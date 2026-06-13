## Context

Taiwan AI Stock Radar 目前技術堆疊：FastAPI (Python) 後端 + Next.js 15 前端 + PostgreSQL + Redis + Docker Compose。已完成的核心骨架包括資料爬取、技術指標計算、SSE 串流、Broker 抽象層、K線形態識別等。

待補齊的八個功能分屬三個層次：
1. **環境設定**（API Key 填入）— 解鎖 AI 評分與 Telegram
2. **後端服務**（TDCC、correlation、stop-loss scheduler）— 數據完整性
3. **前端頁面**（screener、backtest、alerts、PWA）— 使用者可見功能

## Goals / Non-Goals

**Goals:**
- AI 評分真實呼叫 Claude API，結果快取至 Redis
- Telegram 警報從 alert_agent 完整推播至手機
- TDCC 大戶集保週更新，台美連動改為真實計算
- 回測引擎可執行並顯示報告
- 選股工作流（factor-based）前端可操作
- 警報設定 CRUD 完整
- PWA Android 可安裝
- StopLossGuard 每分鐘輪詢上線

**Non-Goals:**
- 元大 API 正式帳戶串接（需客戶實際申請，本階段僅沙盒驗證）
- 期貨選擇權完整模組（PCR/OI）
- 分析記錄側邊欄

## Decisions

**D1：AI 評分快取 key 設計**
用 `ai:score:{symbol}:{date}` 作為 Redis key，TTL 設到隔日 09:00（秒數動態計算）。
理由：同一交易日同一股票結果相同，避免重複呼叫浪費 token。

**D2：Telegram 警報觸發時機**
alert_agent 現有 WebSocket 監控邏輯，改為在 `fetch_tw_market` 每 10 秒回調後，檢查警報條件，觸發時呼叫 `utils/telegram.py:send_message`。
不用 APScheduler 另開任務，因為 tw_market 本身已每 10 秒執行。

**D3：TDCC 爬取策略**
TDCC 每週六公布資料，用 APScheduler cron 週六 10:00 執行。
資料來源：FinMind `TaiwanStockHolding` dataset（已有 API key）。

**D4：台美 rolling correlation**
收盤後 15:15（在 gov_funds 後）計算。
用 Yahoo Finance 抓 S&P500（^GSPC）過去 90 天，對比加權指數，計算 30/60/90 日 Pearson r。
結果寫入 `macro_indicators` table，前端從 API SELECT。

**D5：回測引擎架構**
後端 `backend/backtest/engine.py` 已有骨架。
採向量化回測（pandas），輸入：股票代碼、策略參數、日期範圍；
輸出：trades list、equity curve、勝率/MDD/Sharpe/年化報酬。
前端用 Lightweight Charts 畫 equity curve。

**D6：PWA**
安裝 `next-pwa`，設定 `next.config.ts` 加入 pwa plugin，新增 `public/manifest.json`。
注意：Next.js 16 需用 `@ducanh2912/next-pwa` 而非官方已棄用的 `next-pwa`。

## Risks / Trade-offs

- **ANTHROPIC_API_KEY 未填** → 所有 AI 功能繼續 fallback，不影響系統運作，只影響評分品質。缺口：需使用者手動填入 `.env`。
- **TDCC FinMind 免費版 600次/hr 限制** → 週批次量小，不會觸及上限。
- **回測計算量大** → 長周期回測（5年×全市場）可能超時。Mitigation：限制單次回測最長 2 年，或改為背景任務 + WebSocket 推送進度。
- **next-pwa 與 Next.js 16 相容性** → 需確認版本，`@ducanh2912/next-pwa` 支援 Next.js 15/16。

## Migration Plan

1. 填入 `.env` 中 `ANTHROPIC_API_KEY`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
2. 重啟後端（uvicorn），驗證 `/api/stock/{symbol}/analysis` 回傳真實 AI 評分
3. 部署 TDCC 排程，週六確認資料落地
4. 前端頁面逐一實作，`npm run dev` 驗證
5. PWA 最後加入（不影響其他功能）

## Open Questions

- 元大 API YUANTA_BASE_URL 測試環境 URL 為何？（需使用者提供）
- 回測是否需要支援自訂策略程式碼輸入，或只有預設策略參數？
