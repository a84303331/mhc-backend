"""MHC Backend — HTML 渲染器

將 LLM 產出的 HTML 片段包裝成完整的獨立 HTML 頁面，
帶深色主題、響應式設計，與既有的案例 HTML 風格一致。
"""

from datetime import datetime, timezone, timedelta


# 深色主題 CSS（與 MHC 案例 HTML 風格一致）
DARK_THEME_CSS = """
    :root {
        --bg: #0f0f1a;
        --card-bg: #1a1a2e;
        --text: #e0e0e0;
        --text-secondary: #a0a0b0;
        --accent: #7c3aed;
        --accent-glow: rgba(124, 58, 237, 0.3);
        --border: #2a2a3e;
        --success: #10b981;
        --warning: #f59e0b;
        --code-bg: #1e1e30;
        --code-text: #c4b5fd;
    }

    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC",
                     "PingFang TC", "Microsoft JhengHei", sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.7;
        padding: 2rem 1rem;
        max-width: 800px;
        margin: 0 auto;
    }

    header {
        text-align: center;
        margin-bottom: 2rem;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid var(--border);
    }

    header h1 {
        font-size: 1.5rem;
        color: var(--accent);
        margin-bottom: 0.5rem;
    }

    header .meta {
        font-size: 0.85rem;
        color: var(--text-secondary);
    }

    section {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    section h2 {
        font-size: 1.1rem;
        color: var(--accent);
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    }

    section h3 {
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }

    .hc-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .hc-card:hover {
        border-color: var(--accent);
        box-shadow: 0 0 12px var(--accent-glow);
    }

    .hc-card h3 code {
        background: var(--code-bg);
        color: var(--code-text);
        padding: 0.15em 0.4em;
        border-radius: 4px;
        font-size: 0.9em;
    }

    .match-reason {
        color: var(--text-secondary);
        font-style: italic;
        margin: 0.5rem 0;
        padding-left: 0.5rem;
        border-left: 2px solid var(--accent);
    }

    .action-steps {
        margin-top: 0.5rem;
    }

    ol {
        padding-left: 1.5rem;
    }

    li {
        margin-bottom: 0.5rem;
    }

    code {
        background: var(--code-bg);
        color: var(--code-text);
        padding: 0.1em 0.3em;
        border-radius: 3px;
        font-size: 0.9em;
    }

    footer {
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.8rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border);
    }

    @media (max-width: 640px) {
        body {
            padding: 1rem 0.5rem;
        }
        section {
            padding: 1rem;
        }
    }
"""


def wrap_html(llm_output: str, question: str, user_name: str) -> str:
    """將 LLM 產出的片段包裝成完整 HTML 頁面"""
    now = datetime.now(timezone(timedelta(hours=8)))  # UTC+8
    date_str = now.strftime("%Y-%m-%d %H:%M")

    # 如果 LLM 已經回了完整 HTML（含 <!DOCTYPE>），直接返回
    if llm_output.strip().startswith("<!DOCTYPE") or llm_output.strip().startswith("<html"):
        return llm_output

    # 否則包裝成完整頁面
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MHC 分析 — {question[:30]}...</title>
    <style>{DARK_THEME_CSS}</style>
</head>
<body>
    <header>
        <h1>🧠 Minerva HC 分析</h1>
        <div class="meta">
            提問者：{user_name} · {date_str} · Powered by MHC Engine
        </div>
    </header>

    <section class="question">
        <h2>📝 原始問題</h2>
        <p style="padding: 0.5rem; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--accent);">
            {question}
        </p>
    </section>

    {llm_output}

    <footer>
        <p>Minerva HC Toolkit · AI 輔助分析僅供參考，最終決策權在你手中</p>
        <p>MHC Backend v0.1 · Powered by DeepSeek</p>
    </footer>
</body>
</html>"""


def render_error_html(error_message: str, question: str = "") -> str:
    """渲染錯誤頁面（友善降級）"""
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MHC 分析 — 服務暫時中斷</title>
    <style>{DARK_THEME_CSS}</style>
</head>
<body>
    <header>
        <h1>🛑 MHC 分析引擎暫停服務</h1>
    </header>

    <section style="text-align: center;">
        <p style="font-size: 1.2rem; margin: 2rem 0;">{error_message}</p>
        <p style="color: var(--text-secondary);">
            如果問題持續，請聯繫管理員：hsiachisheng@gmail.com
        </p>
        <p style="color: var(--text-secondary); margin-top: 1rem;">
            你可以稍後再試，分析引擎會自動恢復。
        </p>
    </section>

    <footer>
        <p>MHC Backend v0.1</p>
    </footer>
</body>
</html>"""


def render_offline_html() -> str:
    """PC 端離線時的友善提示頁面（由 Railway 端渲染）"""
    return render_error_html(
        "分析引擎目前離線中，請稍後再試。",
    )
