## Why

Taiwan AI Stock Radar 已完成 Sprint 1–5 的核心架構（資料爬取、指標計算、前端頁面、SSE串流、停損保護、Broker 抽象層、K線形態識別、Self Audit、主力意圖識別、Tauri 桌面殼），但仍有多個功能模組尚未串接或實作，導致 AI 評分、警報推播、自動下單等核心流程無法端對端運作。需要系統性地補齊這些缺口，才能進入 Phase 2（半自動下單）。

## What Changes

- 填入 `ANTHROPIC_API_KEY`，使 AI 評分從 rule-based fallback 升級為真實 Claude API 呼叫
- 串接 Telegram Bot 完整警報邏輯（alert_agent → telegram → 使用者手機）
- 實作 TDCC 大戶集保每週爬取排程
- 修正台美連動係數為真實 rolling correlation（目前前端硬寫假值）
- 完善回測模組（skeleton → 可執行回測並顯示報告）
- 完善選股工作流頁面（`/screener` → factor-based 全市場掃描）
- 完善警報設定頁面（`/alerts` → CRUD + 觸發條件設定）
- 安裝 next-pwa 並設定 PWA manifest（Android 打包）
- 將 StopLossGuard.polling_monitor 掛入 APScheduler
- 元大 API 環境變數補齊並做沙盒測試

## Capabilities

### New Capabilities

- `ai-scoring`: 真實 Claude API 呼叫（claude-sonnet-4-6），結果快取至 Redis TTL 到隔日 09:00
- `telegram-alerts`: 完整警報推播鏈路（alert_agent 觸發 → Telegram Bot → 手機通知）
- `tdcc-chip`: TDCC 大戶集保週爬取，寫入 DB，前端持股分佈顯示
- `us-tw-correlation`: 每日收盤後計算台美 rolling correlation（30/60/90日），取代硬寫值
- `backtest-engine`: 回測引擎可執行，回傳勝率/MDD/夏普，前端圖表顯示
- `screener-factors`: 因子選股（動能/價值/籌碼）全市場掃描，前端工作流頁
- `pwa-android`: next-pwa 安裝、manifest、service worker，可從 Android 安裝為 APP
- `stop-loss-scheduler`: StopLossGuard.polling_monitor 掛入每分鐘排程

### Modified Capabilities

- `alerts-ui`: `/alerts` 頁面從空殼升級為可新增/編輯/刪除警報條件的完整 CRUD UI

## Impact

- `backend/main.py`：新增 TDCC、stop_loss 排程；調整 indicator 排程加入 correlation 計算
- `backend/services/`：新增 `tdcc_fetcher.py`、`correlation_service.py`
- `backend/agents/ai_engine.py`：改為真實呼叫 Claude API，加 Redis 快取
- `backend/routers/alerts.py`：補齊 CRUD endpoint
- `frontend/app/screener/`、`frontend/app/backtest/`、`frontend/app/alerts/`：各頁面實作
- `frontend/`：安裝 next-pwa，新增 `manifest.json`
- `backend/.env`：需補 `ANTHROPIC_API_KEY`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
