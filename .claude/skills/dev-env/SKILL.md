---
name: dev-env
description: 啟動、重啟、除錯 Taiwan Stock Radar 開發環境(Docker 後端 + host Next.js + Tauri)。當改了 .env 或程式碼不生效、需要瀏覽器 preview 驗證、遇到埠衝突、不確定該 restart 還是 force-recreate 時使用。
---

# 開發環境操作

## 拓撲
| 元件 | 位置 | 埠 |
|---|---|---|
| Next.js dev | host(npm run dev) | 3002 |
| FastAPI | Docker `taiwan-stock-radar-fastapi-1` | 8000 |
| Redis | Docker | 6379 |
| Celery worker / Flower | Docker | 5555 |
| Preview 第二實例 | `npm run dev:preview` | 3010 |

Tauri exe 只是開 localhost:3002 的視窗殼(frontendDist 指向 dev server,不打包前端)。前端改動 Ctrl+R 即生效;只有 Rust 殼(src-tauri/)改動才需 `npm run tauri:build`(Rust 冷編譯約 10–15 分鐘)。

## env 兩層載入(最常踩的坑)
容器環境變數 = root `.env`(docker-compose env_file,**優先**)+ `backend/.env`(main.py load_dotenv 補缺,不覆蓋已存在的變數)。
- 改 **root .env** → 必須 `docker compose up -d --force-recreate fastapi`(restart 不會重讀 env_file)
- 改 **backend/.env** → `docker restart taiwan-stock-radar-fastapi-1` 即可(volume mount,進程重啟時重讀)
- 除錯 API key 401 時:比對錯誤訊息裡的 key 尾碼與兩份 .env 的值,判斷容器實際載入的是哪一把、該改哪份檔

## 常用驗證指令
- 健康檢查:`curl http://localhost:8000/api/health`
- 容器 log:`docker logs taiwan-stock-radar-fastapi-1 --tail 30`
- 容器內執行 Python:`docker exec taiwan-stock-radar-fastapi-1 python -c "..."`
- 容器連 host 服務:用 `host.docker.internal`(`172.17.0.1` 不通)
- force-recreate 後容器要先跑 playwright 下載,就緒約 1–2 分鐘,輪詢 /api/health

## Preview MCP(瀏覽器驗證)
`preview_start({name:"frontend"})` → port 3010,與使用者常駐的 3002 **共存**。原理:Next 16 的單一 dev server 鎖以 distDir/lock 為鍵(目錄級,換埠或 pm2 都繞不過),dev:preview 用 `NEXT_DIST_DIR=.next-preview` 分離鎖。
- preview 走 next.config 的 /api 代理,資料正常載入
- SSE 無法在 preview 驗證(後端 CORS 白名單只有 3000–3002);改用 `curl -sN http://localhost:8000/api/stream/signals` 直連驗證
- preview_screenshot 永遠從頁頂擷取;驗證頁面內容用 preview_eval 讀 DOM 更可靠

## 前端 API base 規則(違反必壞)
- 一般 JSON fetch → 相對路徑 `""`(next.config rewrite 代理到 127.0.0.1:8000,免 CORS)
- SSE/EventSource → 直連 `http://localhost:8000`(Next 代理會緩衝串流導致收不到推送)
- 違反的症狀:JSON 用絕對 URL → OPTIONS 400 + net::ERR_FAILED(CORS);SSE 走代理 → 連線開著但 onmessage 永遠不觸發
