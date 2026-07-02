# Taiwan AI Stock Radar

台股波段量化交易系統 — Tauri 桌面 app + Docker 後端,個人專案、單機部署。

## 架構速覽
- 前端:Next.js 16(Turbopack)+ TypeScript,在 host 跑 port 3002(不進 Docker,記憶體不足)
- 後端:FastAPI + APScheduler + Celery(Docker,port 8000);DB 為 SQLite(raw SQL,無 ORM);Redis 快取
- AI:DeepSeek(評分/多空辯論/IC 備忘錄)、Gemini Vision(截圖辨識持倉,fallback Groq)
- 桌面殼:Tauri 2 — 只是開 localhost:3002 的視窗,**不打包前端**;前端改動 Ctrl+R 即生效,只有 src-tauri/ 改動才需重 build exe
- 啟動/重啟/env 陷阱/preview → skill `dev-env`;資料回填/外部 API 限制 → skill `data-pipeline`

## 開發規則
- 前端 API base:一般 JSON fetch 用相對路徑(走 next.config 的 /api 代理,免 CORS);SSE/EventSource **直連** http://localhost:8000(代理會緩衝串流)
- Tauri WebView 擋 target="_blank":開外部網址用 opener plugin(已裝,見 TradingViewModal)或 iframe 內嵌
- 技術指標收盤後預算寫入 stock_indicators_daily;API 端點只 SELECT,不即時計算
- AI 結果快取 Redis,TTL 至隔日 09:00
- 不 commit .env(root 與 backend/ 兩份都被 gitignore);新增服務/依賴時同步更新 start-dev.bat 與 啟動開發環境.bat
- Commit 訊息繁體中文,格式 `feat/fix(scope): 描述`
- 個股頁 frontend/app/stock/page.tsx 版面是使用者手調的,改動前先確認有無未提交變更

## 風控紅線(絕對不能違反)
- 單筆損失上限:總資產 2%;單股持有上限:總資產 10%
- AI 評分 < 70 不自動下單;台指期結算前 2 天禁止自動下單;當日虧損 > 5% 自動停止交易

## 已知陷阱
- TWSE MIS 即時報價每 5 秒限 3 次,超過封 IP
- FinMind 免費 register 等級:除權息 dataset 無權限(HTTP 400)、其餘額度易 402 → 優先用 TWSE OpenAPI 免費源(財報日曆已改)
- TradingView 台股代號格式:`TWSE:2330`
- 元大 YuantaSparkAPI:需 IP 白名單 + CA 憑證年更;`YUANTA_SIMULATION=true` 為預設模擬模式
- uvicorn --reload 在 Windows 偶爾不偵測變更,改檔沒生效先重啟容器
- Next 16 同目錄單一 dev server 鎖(distDir/lock):第二實例用 `npm run dev:preview`(NEXT_DIST_DIR 分離,已設好),換埠無效

## 文件地圖
- `docs/00–07*.md`:設計文件;`docs/PLAN.md`:Phase 歷史;`docs/archive/`:過時快照與提案(勿作現況依據)
- `openspec/`:change 管理(/opsx:* 指令)
- 跨 session 事實記憶在使用者層 memory;操作程序在 `.claude/skills/`
