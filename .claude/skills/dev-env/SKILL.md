---
name: dev-env
description: 啟動、重啟、除錯 Taiwan Stock Radar 開發環境(host venv 後端 + host Next.js + Tauri)。當改了 .env 或程式碼不生效、需要瀏覽器 preview 驗證、遇到埠衝突時使用。
---

# 開發環境操作

## 拓撲(2026-07-04 起全 host,無 Docker)
| 元件 | 位置 | 埠 |
|---|---|---|
| Next.js dev | host(npm run dev) | 3002 |
| FastAPI | host(backend\.venv uvicorn) | 8000 |
| Preview 第二實例 | `npm run dev:preview` | 3010 |

- 一鍵啟動:雙擊 `啟動開發環境.bat`(= start-dev.bat):起後端+前端、等就緒、自動開 Tauri exe(找不到 exe 則開瀏覽器)。停止:`停止開發環境.bat`
- Tauri exe 也是啟動器:main.rs 會檢查 8000/3002,**埠空著才 spawn** 對應服務(bat 先起不會雙重啟動)。直接雙擊 exe 也能一鍵啟動,但不等就緒,首畫面可能要 Ctrl+R
- Redis/Celery 已移除:快取走 services/kv_store.py(SQLite cache 表)+行程內記憶體;TradingView 訊號 SSE 走 services/signal_bus.py(行程內)
- Tauri exe 只是開 localhost:3002 的視窗殼(frontendDist 指向 dev server,不打包前端)。前端改動 Ctrl+R 即生效;只有 Rust 殼(src-tauri/)改動才需 `npm run tauri:build`(Rust 冷編譯約 10–15 分鐘)

## env 載入
host 後端只讀 `backend/.env`(main.py load_dotenv)。root `.env` 只剩 docker-compose 用(平常用不到)。
- 改 **backend/.env** → 重啟後端(uvicorn --reload 不會因 .env 變更觸發 reload)
- 除錯 API key 401 時:比對錯誤訊息裡的 key 尾碼與 backend/.env 的值

## 常用驗證指令
- 健康檢查:`curl http://localhost:8000/api/health`(正常回 `"redis":"disabled"`)
- 後端 log:看「FastAPI Backend」PowerShell 視窗(bat 開的)
- host 執行 Python:`backend\.venv\Scripts\python.exe -c "..."`(在 backend/ 目錄下執行,DB 相對路徑才對)
- DB 檔:`backend\data\stockradar.db`(db.py 預設;舊 AppData\Roaming\com.taiwan.ai.stock.radar\ 那份已棄用)
- CMoney 爬蟲需 host 有 playwright chromium(已裝於 %LOCALAPPDATA%\ms-playwright)

## Preview MCP(瀏覽器驗證)
`preview_start({name:"frontend"})` → port 3010,與使用者常駐的 3002 **共存**。原理:Next 16 的單一 dev server 鎖以 distDir/lock 為鍵(目錄級,換埠或 pm2 都繞不過),dev:preview 用 `NEXT_DIST_DIR=.next-preview` 分離鎖。
- preview 走 next.config 的 /api 代理,資料正常載入
- SSE 無法在 preview 驗證(後端 CORS 白名單只有 3000–3002);改用 `curl -sN http://localhost:8000/api/stream/signals` 直連驗證
- preview_screenshot 永遠從頁頂擷取;驗證頁面內容用 preview_eval 讀 DOM 更可靠

## 前端 API base 規則(違反必壞)
- 一般 JSON fetch → 相對路徑 `""`(next.config rewrite 代理到 127.0.0.1:8000,免 CORS)
- SSE/EventSource → 直連 `http://localhost:8000`(Next 代理會緩衝串流導致收不到推送)
- 違反的症狀:JSON 用絕對 URL → OPTIONS 400 + net::ERR_FAILED(CORS);SSE 走代理 → 連線開著但 onmessage 永遠不觸發
