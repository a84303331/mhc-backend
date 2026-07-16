"""MHC Backend — FastAPI 主程式

PC 端 MHC 推理引擎 API 服務。
提供 /health 健康檢查和 /ask 分析端點。
透過 Cloudflare Tunnel 對外暴露給 Railway。
"""

import os
import re
import time
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from obsidian_reader import ObsidianReader
from mhc_engine import MHCInferenceEngine, LLMUnavailableError
from html_renderer import wrap_html, render_error_html

load_dotenv()

# ── Config ──────────────────────────────────────────
MHC_API_TOKEN = os.getenv("MHC_API_TOKEN", "change-me")
OBSIDIAN_VAULT_PATH = os.getenv(
    "OBSIDIAN_VAULT_PATH", "/mnt/d/Obsidian/Doc_Obsidian/Summer_sync"
)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))

# ── Logging ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mhc-backend")

# ── Init ────────────────────────────────────────────
reader = ObsidianReader(OBSIDIAN_VAULT_PATH)
engine = MHCInferenceEngine(reader)

# ── App ─────────────────────────────────────────────
app = FastAPI(
    title="MHC Backend",
    description="Minerva HC 推理引擎 — PC 端 API",
    version="0.1.0",
)

# CORS（Railway 跨域呼叫）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mhc.summer-hsia.com",
        "https://summer-hsia.com",
        "http://localhost:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Models ──────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="使用者問題")
    user_name: str = Field(default="使用者", max_length=50)
    case_id: str = Field(default="", max_length=64, description="案例 ID")


class AskResponse(BaseModel):
    html: str = Field(..., description="完整 MHC 分析 HTML")
    hcs_used: list[str] = Field(default_factory=list)
    biases_detected: list[str] = Field(default_factory=list)
    llm_latency_ms: int = 0


class HealthResponse(BaseModel):
    status: str
    vault_accessible: bool
    vault_details: dict
    llm_configured: bool
    uptime_seconds: float


class FeedbackRequest(BaseModel):
    case_id: str = Field(..., min_length=1, max_length=64, description="案例 ID")
    insight: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    actionability: int = Field(..., ge=1, le=5)
    overall: int = Field(..., ge=1, le=5)
    reuse_intent: int = Field(..., ge=1, le=5)


class ErrorResponse(BaseModel):
    error: str
    message: str


# ── Auth ────────────────────────────────────────────
def verify_token(authorization: Optional[str] = Header(None)) -> None:
    """驗證 Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != MHC_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")


# ── Startup ─────────────────────────────────────────
_start_time = time.time()


@app.on_event("startup")
async def startup():
    logger.info(f"MHC Backend starting on {HOST}:{PORT}")
    logger.info(f"Obsidian vault: {OBSIDIAN_VAULT_PATH}")
    logger.info(f"Vault accessible: {reader.is_accessible}")


# ── Helpers ─────────────────────────────────────────
def html_to_text(html: str) -> str:
    """簡單 HTML → 純文字轉換"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_case_to_vault(case_id: str, question: str, user_name: str, html: str) -> dict:
    """將案例存檔到 Obsidian vault 的 案例html 和 案例md 目錄"""
    if not case_id:
        return {"saved": False, "reason": "no case_id"}

    import pathlib
    vault = pathlib.Path(OBSIDIAN_VAULT_PATH)
    html_dir = vault / "1_Projects" / "minerva-hc-toolbox" / "案例 HTML"
    md_dir = vault / "1_Projects" / "minerva-hc-toolbox" / "案例 MD"
    html_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # 儲存完整 HTML
    html_path = html_dir / f"{case_id}.html"
    full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{case_id} — {question[:40]}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 1rem; background: #1a1a2e; color: #e0e0e0; }}
  h1 {{ color: #7c3aed; font-size: 1.3rem; }}
  .meta {{ color: #888; font-size: 0.8rem; margin-bottom: 1.5rem; }}
  .question {{ background: #16213e; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; border-left: 3px solid #7c3aed; }}
</style>
</head>
<body>
<h1>MHC 案例分析：{case_id}</h1>
<div class="meta">提問者：{user_name}｜日期：{now}｜問題字數：{len(question)} 字</div>
<div class="question"><strong>📝 原始問題：</strong><br>{question}</div>
{html}
</body>
</html>"""
    html_path.write_text(full_html, encoding="utf-8")

    # 儲存 Markdown
    md_path = md_dir / f"{case_id}.md"
    text_summary = html_to_text(html)
    text_preview = text_summary[:500] + ("..." if len(text_summary) > 500 else "")
    md_content = f"""---
case_id: {case_id}
question: "{question[:80]}{'...' if len(question) > 80 else ''}"
user_name: {user_name}
date: {now}
type: mhc-case
tags: [mhc, case, minerva-hc]
---

# {case_id}

> **提問者**：{user_name}
> **日期**：{now}
> **問題**：{question}

## 📄 完整 HTML

→ [{case_id}.html](../案例%20HTML/{case_id}.html)

## 📝 分析內容（文字摘要）

{text_preview}

---

*此案例由 MHC（Minerva Habits of Mind & Cognitive Bias Toolbox）自動分析產生。*
"""
    md_path.write_text(md_content, encoding="utf-8")

    logger.info(f"case_saved case_id={case_id} html={html_path} md={md_path}")
    return {
        "saved": True,
        "html_path": str(html_path),
        "md_path": str(md_path),
    }


def update_case_with_feedback(
    case_id: str,
    insight: int,
    clarity: int,
    actionability: int,
    overall: int,
    reuse_intent: int,
) -> dict:
    """將使用者評分寫入既有的案例 HTML 和 MD 檔案"""
    import pathlib

    vault = pathlib.Path(OBSIDIAN_VAULT_PATH)
    html_dir = vault / "1_Projects" / "minerva-hc-toolbox" / "案例 HTML"
    md_dir = vault / "1_Projects" / "minerva-hc-toolbox" / "案例 MD"

    html_path = html_dir / f"{case_id}.html"
    md_path = md_dir / f"{case_id}.md"

    if not html_path.exists() and not md_path.exists():
        logger.warning(f"update_feedback: case not found case_id={case_id}")
        return {"updated": False, "reason": "case_not_found"}

    dim_labels = {
        "insight": "洞察有用性",
        "clarity": "框架清晰度",
        "actionability": "行動可行性",
        "overall": "整體品質",
        "reuse_intent": "再使用意願",
    }
    ratings = {
        "insight": insight,
        "clarity": clarity,
        "actionability": actionability,
        "overall": overall,
        "reuse_intent": reuse_intent,
    }
    avg = round(sum(ratings.values()) / len(ratings), 1)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── 更新 HTML ──
    if html_path.exists():
        html_content = html_path.read_text(encoding="utf-8")

        # 生成評分 HTML
        stars_html = ""
        for key, label in dim_labels.items():
            v = ratings[key]
            filled = "★" * v + "☆" * (5 - v)
            stars_html += (
                f'<div class="feedback-row">'
                f'<span class="feedback-dim">{label}</span>'
                f'<span class="feedback-stars">{filled}</span>'
                f'<span class="feedback-score">{v}/5</span>'
                f"</div>\n"
            )

        feedback_html = f"""
<div class="feedback-section" style="margin-top:2rem;padding:1.5rem;background:#16213e;border-radius:12px;border:1px solid #333;">
<h3 style="color:#f59e0b;margin-bottom:0.75rem;">📊 使用者評分</h3>
<div style="margin-bottom:0.5rem;color:#888;font-size:0.85rem;">提交時間：{now}｜綜合平均：{avg}/5</div>
{stars_html}
</div>"""

        # 插入到 </body> 之前
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", feedback_html + "\n</body>")
        else:
            html_content += feedback_html

        html_path.write_text(html_content, encoding="utf-8")
        logger.info(f"feedback_html_updated case_id={case_id}")

    # ── 更新 Markdown ──
    if md_path.exists():
        md_content = md_path.read_text(encoding="utf-8")

        # 加入評分 section（避免重複寫入）
        if "## 📊 使用者評分" not in md_content:
            stars_md = ""
            for key, label in dim_labels.items():
                v = ratings[key]
                filled = "★" * v + "☆" * (5 - v)
                stars_md += f"| {label} | {filled} | {v}/5 |\n"

            feedback_md = f"""
## 📊 使用者評分

> 提交時間：{now}｜綜合平均：{avg}/5

| 評分項目 | 評分 | 分數 |
|----------|------|------|
{stars_md}
"""
            md_content += feedback_md
            md_path.write_text(md_content, encoding="utf-8")
            logger.info(f"feedback_md_updated case_id={case_id}")

    return {"updated": True, "avg": avg, "time": now}


# ── Endpoints ───────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    """健康檢查端點 — Railway 定期 ping 用"""
    vault_checks = reader.health_check()
    return HealthResponse(
        status="ok" if vault_checks["vault_accessible"] else "degraded",
        vault_accessible=vault_checks["vault_accessible"],
        vault_details=vault_checks,
        llm_configured=bool(os.getenv("LLM_API_KEY")),
        uptime_seconds=time.time() - _start_time,
    )


@app.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    authorization: Optional[str] = Header(None),
):
    """MHC 分析端點 — 接收問題，回傳 HTML

    Railway 端會轉發使用者問題到此端點。
    需要 Bearer token 驗證（內部 API 使用）。
    """
    # 驗證 token
    verify_token(authorization)

    logger.info(f"Ask request from '{req.user_name}': {req.question[:80]}...")

    try:
        result = engine.analyze(req.question, req.user_name)
        # 包裝成完整 HTML
        result["html"] = wrap_html(result["html"], req.question, req.user_name)
        logger.info(
            f"Analysis complete: {len(result['hcs_used'])} HCs, "
            f"{len(result['biases_detected'])} biases, "
            f"{result['llm_latency_ms']}ms"
        )
        # 存檔到 Obsidian vault
        save_result = save_case_to_vault(
            req.case_id, req.question, req.user_name, result["html"]
        )
        return AskResponse(**result)

    except LLMUnavailableError as e:
        logger.error(f"LLM unavailable: {e}")
        html = render_error_html(str(e), req.question)
        return AskResponse(
            html=html,
            hcs_used=[],
            biases_detected=[],
            llm_latency_ms=0,
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="推理引擎內部錯誤")


@app.post("/feedback")
async def save_feedback(
    req: FeedbackRequest,
    authorization: str = Header(None),
):
    """接收使用者評分，寫入 Obsidian 案例檔案

    Railway 端在儲存評分到 DB 後，呼叫此端點同步更新案例檔案。
    """
    verify_token(authorization)

    logger.info(
        f"Feedback received: case_id={req.case_id} "
        f"insight={req.insight} clarity={req.clarity} "
        f"actionability={req.actionability} overall={req.overall} "
        f"reuse_intent={req.reuse_intent}"
    )

    try:
        result = update_case_with_feedback(
            req.case_id,
            req.insight,
            req.clarity,
            req.actionability,
            req.overall,
            req.reuse_intent,
        )
        if result["updated"]:
            return {"status": "ok", "avg": result["avg"], "time": result["time"]}
        else:
            return {"status": "skipped", "reason": result.get("reason", "unknown")}

    except Exception as e:
        logger.exception(f"Failed to update case with feedback: {e}")
        raise HTTPException(status_code=500, detail="寫入案例失敗")


# ── Direct HTML access (for testing) ────────────────
@app.get("/test")
async def test_page():
    """測試頁面 — 直接瀏覽器確認服務運行"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>MHC Backend Test</title>
        <style>
            body { font-family: sans-serif; max-width: 600px; margin: 2rem auto; padding: 1rem; }
            h1 { color: #7c3aed; }
            textarea { width: 100%; height: 100px; margin: 1rem 0; }
            button { padding: 0.5rem 1rem; background: #7c3aed; color: white; border: none; border-radius: 4px; cursor: pointer; }
            #result { margin-top: 1rem; padding: 1rem; background: #f5f5f5; border-radius: 4px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <h1>🧠 MHC Backend — 測試頁面</h1>
        <p>服務運行中。輸入問題測試分析引擎：</p>
        <textarea id="question" placeholder="輸入你的問題..."></textarea>
        <br>
        <input id="name" placeholder="你的名字" value="測試者" style="margin-right: 0.5rem;">
        <button onclick="test()">送出分析</button>
        <div id="result"></div>
        <script>
        async function test() {
            const q = document.getElementById('question').value;
            const n = document.getElementById('name').value;
            document.getElementById('result').textContent = '分析中...';
            try {
                const resp = await fetch('/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: q, user_name: n })
                });
                const data = await resp.json();
                const win = window.open('', '_blank');
                win.document.write(data.html);
            } catch(e) {
                document.getElementById('result').textContent = '錯誤: ' + e.message;
            }
        }
        </script>
    </body>
    </html>
    """)


# ── Main ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")
