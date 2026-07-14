# MHC Backend

Minerva HC 推理引擎 — PC 端 API 服務。

透過 Cloudflare Tunnel 對外暴露，供 Railway 上的 MHC Web App 呼叫。

## 架構

```
Railway (Web App) → Cloudflare Tunnel → api.summer-hsia.com → localhost:8001
```

## 快速開始（10 分鐘內）

```bash
# 1. Clone
git clone https://github.com/a84303331/mhc-backend.git
cd mhc-backend

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 LLM_API_KEY 和 MHC_API_TOKEN

# 3. 安裝依賴
uv sync

# 4. 啟動
uv run uvicorn main:app --host 0.0.0.0 --port 8001
```

## 健康檢查

```bash
curl http://localhost:8001/health
```

## API 端點

| 端點 | 方法 | 說明 | 驗證 |
|------|------|------|------|
| `/health` | GET | 健康檢查 | 無 |
| `/ask` | POST | MHC 分析 | Bearer Token |
| `/test` | GET | 瀏覽器測試頁 | 無 |

### POST /ask

```bash
curl -X POST http://localhost:8001/ask \
  -H "Authorization: Bearer $MHC_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "客戶在颱風天要求破例上廣告，我該怎麼回？", "user_name": "張三"}'
```

## 檔案結構

```
mhc-backend/
├── main.py              # FastAPI 主程式
├── mhc_engine.py        # MHC 推理核心（prompt 組裝 + LLM 呼叫）
├── obsidian_reader.py   # 讀取 Obsidian vault
├── html_renderer.py     # HTML 頁面渲染
├── pyproject.toml       # uv 專案設定
├── .env.example         # 環境變數範本
├── .env                 # 實際環境變數（不進 git）
├── .gitignore
└── README.md
```

## 技術棧

- Python 3.11+
- FastAPI + uvicorn
- httpx（LLM API 呼叫）
- Jinja2（模板渲染）
- Obsidian vault（知識庫來源）

## 環境變數

| 變數 | 說明 | 必填 |
|------|------|:--:|
| `LLM_API_KEY` | DeepSeek API key | ✅ |
| `LLM_BASE_URL` | LLM API 端點 | - |
| `LLM_MODEL` | 模型名稱 | - |
| `MHC_API_TOKEN` | 內部 API 驗證 token | ✅ |
| `OBSIDIAN_VAULT_PATH` | Obsidian vault 路徑 | ✅ |

## License

Private project. All rights reserved.
