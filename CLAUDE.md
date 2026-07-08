# Taiwan AI Stock Radar

台股波段量化交易系統 — Tauri 桌面 app + host venv 後端，個人專案、單機部署。
本檔是**路由中心**：只放架構、紅線、路由表。細節一律在指向的檔案裡，不要往這裡加長內容（規則見 harness/F）。

## 架構速覽
- 前端：Next.js 16（Turbopack）+ TypeScript，在 host 跑 port 3002（不進 Docker，記憶體不足）
- 後端：FastAPI + APScheduler，host venv 直跑（port 8000，**不用 Docker**；Redis/Celery 已於 2026-07-04 移除）；DB 為 SQLite（raw SQL，無 ORM，backend/data/stockradar.db）；快取＝行程內記憶體＋SQLite cache 表（services/kv_store.py）
- AI：DeepSeek（評分/多空辯論/IC 備忘錄）、Gemini Vision（截圖辨識持倉，fallback Groq）
- 桌面殼：Tauri 2 — 只是開 localhost:3002 的視窗，**不打包前端**；前端改動 Ctrl+R 即生效，只有 src-tauri/ 改動才需重 build exe

## 風控紅線（絕對不能違反，改任何下單/風控相關代碼前重讀一次）
- 單筆損失上限：總資產 2%；單股持有上限：總資產 10%
- AI 評分 < 70 不自動下單；台指期結算前 2 天禁止自動下單；當日虧損 > 5% 自動停止交易
- 涉及這些數值或下單邏輯的改動 → 一律先問 User（harness/D 第 3 節）

## 開發規則（核心，違反必壞）
- 前端 API base：一般 JSON fetch 用相對路徑（走 next.config 的 /api 代理）；SSE/EventSource **直連** http://localhost:8000（代理會緩衝串流）。細節與症狀 → skill `dev-env`
- Tauri WebView 擋 target="_blank"：開外部網址用 opener plugin（見 TradingViewModal）
- 技術指標收盤後預算寫入 stock_indicators_daily；API 端點只 SELECT，不即時計算
- AI 結果快取 SQLite cache 表（services/kv_store.py），TTL 至隔日 09:00
- 不 commit .env（root 與 backend/ 兩份都被 gitignore）；新增服務/依賴時同步更新 start-dev.bat 與 啟動開發環境.bat
- Commit 訊息繁體中文，格式 `feat/fix(scope): 描述`
- 個股頁 frontend/app/stock/page.tsx 版面是使用者手調的，改動前先確認有無未提交變更

## Harness 路由表（工作流制度，.claude/harness/）

| 情境 | 必讀 |
|---|---|
| 要派 subagent（搜尋/實作/驗證） | harness/C-model-dispatch.md + E-dispatch-templates.md |
| 卡關、同一個錯修了兩次還在 | harness/D-judgment-checklist.md 第 1 節 |
| 準備宣告「完成」 | harness/D-judgment-checklist.md 第 2 節（有指令的驗收才算數） |
| 不確定該不該問 User | harness/D-judgment-checklist.md 第 3 節 |
| debug 開始前 / 結束後 | harness/pitfalls.md（先查坑；解題超過 3 輪工具呼叫才記坑，條件見 F 第 2 節） |
| 想修改任何 harness/規則檔 | harness/F-knowledge-protocol.md（權限分層） |
| 新 session 首次接手 | harness/G-handover.md |

## 技能與工具白名單（本專案）
- 允許自動觸發：`dev-env`（啟動/重啟/env/preview）、`data-pipeline`（回填/外部 API）、`/opsx:*`（openspec change 管理）、內建 `verify`/`code-review`
- **白名單外的技能不得自動觸發**（gstack、superpowers 等全域套件），除非 User 明確點名
- **禁止呼叫 `mcp__agentmemory__*`**：記憶唯一正典是檔案 memory（使用者層）＋ `.claude/harness/`（制度）＋ `.claude/skills/`（程序）

## 已知陷阱（只列跨領域的；資料源/API 限制細節 → skill `data-pipeline`）
- TWSE MIS 即時報價每 5 秒限 3 次，超過封 IP
- TradingView 台股代號格式：`TWSE:2330`
- uvicorn --reload 在 Windows 偶爾不偵測變更，改檔沒生效先重啟後端（關掉 FastAPI 視窗重開 bat）
- Next 16 同目錄單一 dev server 鎖：第二實例用 `npm run dev:preview`（NEXT_DIST_DIR 分離，已設好），換埠無效
- 元大 YuantaSparkAPI：需 IP 白名單 + CA 憑證年更；`YUANTA_SIMULATION=true` 為預設模擬模式

## 文件地圖
- `.claude/harness/`：工作流制度（Fable 5 於 2026-07-03 建立，README.md 是索引）
- `docs/00–07*.md`：設計文件；`docs/PLAN.md`：Phase 歷史；`docs/archive/`：過時快照（勿作現況依據）
- `openspec/`：change 管理（/opsx:* 指令）
- 跨 session 事實記憶在使用者層 memory；操作程序在 `.claude/skills/`
