"""MHC Backend — 推理引擎

將 MHC skill 的分析框架封裝為結構化 prompt，呼叫 LLM API 進行推理。
包含 retry with exponential backoff、token 超限降級、錯誤處理。
"""

import os
import time
import logging
from typing import Optional

import httpx
from dotenv import load_dotenv

from obsidian_reader import ObsidianReader

load_dotenv()

logger = logging.getLogger(__name__)

# LLM 設定
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# MHC 系統 prompt（核心分析框架，取自 skill 行為邏輯）
MHC_SYSTEM_PROMPT = """你是一位 Minerva Habits of Mind（思維習慣）專家顧問。

Minerva 大學開發了 79 個 Habits of Mind & Foundational Concepts（HCs），
是結構化的思考工具，用於解決決策困境、溝通障礙、創造瓶頸、人際衝突等問題。

## 分析框架（Ambrose 五階段）

收到使用者問題後，依序經過五個階段：

1. **情境識別**：判斷問題屬於哪個路徑（決策/評估/創意/自學/溝通/談判/系統/倫理）
2. **HC 匹配**：從 HC 清單中選擇 2-4 個最相關的 HC
3. **偏誤診斷**：若問題涉及明顯認知偏誤，標註並配對矯正 HC
4. **組合技建構**：說明選定 HC 如何組合使用
5. **行動建議**：給出具體、可執行的下一步（含優先級 ⭐）

## 輸出格式

用 HTML 輸出（深色主題），結構為：

```html
<div class="mhc-analysis">
  <section class="diagnosis">
    <h2>🔍 情境診斷</h2>
    <p>路徑識別 + 核心困境一句話</p>
  </section>

  <section class="hc-recommendations">
    <h2>🧠 思考處方</h2>
    <!-- 每個 HC 一個卡片 -->
    <div class="hc-card">
      <h3><code>#tag</code> — 一句話定義</h3>
      <p class="match-reason">為何匹配你的情境</p>
      <div class="action-steps">
        <p>→ 核心操作：具體可執行的步驟</p>
      </div>
    </div>
  </section>

  <section class="combo">
    <h2>🔄 組合技</h2>
    <p>這些 HC 如何協同運作</p>
  </section>

  <section class="action-plan">
    <h2>📋 行動計畫</h2>
    <ol>
      <li>⭐ 最重要的一步</li>
      <li>第二步</li>
      <li>後續追蹤建議</li>
    </ol>
  </section>
</div>
```

## 核心原則

- 一次不超過 4 個 HC（資訊過載會降低效果）
- 每個 HC 必須附上「為何匹配此情境」的理由
- 行動建議必須具體可執行，不是抽象雞湯
- 語氣專業但溫暖，像智者而非醫生
- 繁體中文輸出
"""


class MHCError(Exception):
    """MHC 引擎錯誤"""
    pass


class LLMUnavailableError(MHCError):
    """LLM 不可用（重試耗盡後）"""
    pass


class MHCInferenceEngine:
    """MHC 推理引擎：讀取知識庫 → 組裝 prompt → 呼叫 LLM → 回傳 HTML"""

    def __init__(self, reader: ObsidianReader):
        self.reader = reader
        self.client = httpx.Client(timeout=60.0)

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> str:
        """呼叫 LLM API，含 retry with exponential backoff"""
        last_error = None

        for attempt in range(3):
            try:
                response = self.client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                elif response.status_code == 429:
                    # Rate limit — exponential backoff
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                    last_error = response.text

                elif response.status_code == 400:
                    # Token 超限 — 縮短後重試一次
                    if attempt == 0 and max_tokens > 1024:
                        logger.warning("Token limit, retrying with shorter context")
                        return self._call_llm(
                            system_prompt[:2000],  # 截斷 system prompt
                            user_message[:2000],    # 截斷 user message
                            max_tokens=2048,
                        )
                    last_error = response.text
                    break  # 不再重試

                elif response.status_code == 404:
                    logger.error(f"Model not found: {response.text}")
                    last_error = response.text
                    break

                else:
                    logger.error(f"LLM API error {response.status_code}: {response.text}")
                    last_error = response.text
                    if attempt < 2:
                        time.sleep(1)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Connection error (attempt {attempt+1}/3): {e}")
                last_error = str(e)
                if attempt < 2:
                    time.sleep(2 ** attempt)

        logger.error(f"All retries exhausted. Last error: {last_error}")
        raise LLMUnavailableError("分析引擎暫時忙碌中，請 5 分鐘後再試")

    def build_prompt(self, question: str, user_name: str = "使用者") -> str:
        """組裝完整 prompt：知識庫內容 + 使用者問題"""
        parts = []

        # 1. HC 清單摘要（只取 tag + 一句話定義）
        hc_master = self.reader.get_hc_master_list()
        if hc_master:
            # 只取前 3000 字（79 個 HC 的定義摘要）
            parts.append("## HC 清單（節選）\n")
            parts.append(hc_master[:3000])
            parts.append("\n---\n")

        # 2. 偏誤對照表摘要
        bias_mapping = self.reader.get_bias_hc_mapping()
        if bias_mapping:
            parts.append("## 偏誤↔HC 對照（節選）\n")
            parts.append(bias_mapping[:1500])
            parts.append("\n---\n")

        # 3. 相似案例（few-shot）
        cases_text = self.reader.get_recent_cases_text(max_cases=3, max_chars=2500)
        if cases_text:
            parts.append("## 相關案例分析（參考風格）\n")
            parts.append(cases_text)
            parts.append("\n---\n")

        # 4. 使用者問題
        parts.append(f"## 使用者問題（來自 {user_name}）\n")
        parts.append(f"> {question}\n")
        parts.append("\n請依 Ambrose 五階段分析框架，使用深色主題 HTML 格式回覆。")

        return "\n".join(parts)

    def analyze(self, question: str, user_name: str = "使用者") -> dict:
        """執行完整 MHC 分析流程

        Returns:
            {
                "html": "<完整 HTML>",
                "hcs_used": ["#tag1", "#tag2", ...],
                "biases_detected": ["偏誤名稱1", ...],
                "llm_latency_ms": 1234
            }
        """
        start_time = time.time()

        # 組裝 prompt
        user_prompt = self.build_prompt(question, user_name)

        # 呼叫 LLM
        html_output = self._call_llm(MHC_SYSTEM_PROMPT, user_prompt)

        latency_ms = int((time.time() - start_time) * 1000)

        # 簡易解析 HC tags（從 LLM 輸出中提取）
        import re
        hc_tags = re.findall(r'#([a-z]+)', html_output)
        hcs_used = list(set(f"#{t}" for t in hc_tags if len(t) > 2))[:6]

        # 簡易解析偏誤（如果 LLM 提到）
        bias_patterns = [
            "沉沒成本", "雙曲貼現", "現狀偏誤", "確認偏誤", "從眾效應",
            "錨定效應", "過度自信", "損失規避", "框架效應", "可得性啟發",
            "基本歸因謬誤", "後見之明", "自利偏誤", "光環效應",
        ]
        biases_detected = [b for b in bias_patterns if b in html_output]

        return {
            "html": html_output,
            "hcs_used": hcs_used,
            "biases_detected": biases_detected,
            "llm_latency_ms": latency_ms,
        }
