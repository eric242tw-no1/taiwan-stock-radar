## 1. 環境設定（解鎖 AI + Telegram）

- [x] 1.1 在 `backend/.env` 填入 `ANTHROPIC_API_KEY`
- [x] 1.2 在 `backend/.env` 填入 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`
- [x] 1.3 重啟後端，確認 `/api/stock/2330/analysis` 回傳真實 AI 評分（非 rule-based）
- [x] 1.4 發送測試訊息確認 Telegram Bot 推播正常

## 2. AI 評分 Redis 快取

- [x] 2.1 修改 `backend/agents/ai_engine.py`：呼叫前先查 Redis `ai:score:{symbol}:{date}`
- [x] 2.2 計算 TTL 至隔日 09:00（動態秒數），呼叫後結果寫入 Redis
- [x] 2.3 新增 `GET /api/stock/{symbol}/ai-score` endpoint（直接讀快取）

## 3. Telegram 警報完整鏈路

- [x] 3.1 修改 `backend/agents/alert_agent.py`：觸發條件成立時呼叫 `utils/telegram.send_message`
- [x] 3.2 在 `fetch_tw_market` 每 10 秒回調後加入警報條件檢查
- [ ] 3.3 測試：手動觸發警報，確認手機收到 Telegram 通知
- [x] 3.4 完善 `backend/routers/alerts.py` CRUD：`POST /api/alerts`、`PUT /api/alerts/{id}`、`DELETE /api/alerts/{id}`

## 4. TDCC 大戶集保爬取

- [x] 4.1 新增 `backend/services/tdcc_fetcher.py`：透過 FinMind `TaiwanStockHolding` 抓週資料
- [x] 4.2 設計 `stock_holding_distribution` DB table（symbol, date, level, ratio）
- [x] 4.3 在 `backend/main.py` 加入 APScheduler cron job（每週六 10:00）
- [x] 4.4 新增 `GET /api/stock/{symbol}/chip-distribution` endpoint

## 5. 台美連動真實計算

- [x] 5.1 新增 `backend/services/correlation_service.py`：下載 ^GSPC + 台灣加權指數，計算 30/60/90 日 Pearson r
- [x] 5.2 建立 `macro_indicators` DB table（date, tw_us_corr_30d, tw_us_corr_60d, tw_us_corr_90d）
- [x] 5.3 在 `backend/main.py` 加入每日 15:15 排程
- [x] 5.4 修改 `frontend/app/page.tsx`：台美連動從 API 讀取，取代硬寫值

## 6. StopLossGuard 排程上線

- [x] 6.1 在 `backend/main.py` 建立全域 `YuantaBroker` 實例（simulation=true）
- [x] 6.2 初始化 `StopLossGuard(broker)` 為全域單例
- [x] 6.3 加入 APScheduler interval job：每分鐘呼叫 `stop_loss_guard.polling_monitor()`
- [x] 6.4 新增 `GET /api/risk/watching` endpoint 回傳目前監控中的股票清單

## 7. 回測引擎實作

- [x] 7.1 完善 `backend/backtest/engine.py`：輸入 symbol/strategy/date_range，輸出 trades/equity_curve/metrics
- [x] 7.2 實作預設策略：MA 黃金交叉、RSI 超買超賣
- [x] 7.3 完善 `backend/routers/backtest.py`：`POST /api/backtest/run`（背景任務 + 結果 ID）
- [x] 7.4 新增 `GET /api/backtest/{result_id}` 查詢結果
- [x] 7.5 完善 `frontend/app/backtest/page.tsx`：參數輸入表單 + Lightweight Charts equity curve

## 8. 選股工作流頁面

- [x] 8.1 完善 `backend/agents/screener_agent.py`：支援動能因子（近20日報酬率）、籌碼因子（外資連買）
- [x] 8.2 完善 `backend/routers/screener.py`：`POST /api/screener/run` 回傳排序後候選清單
- [x] 8.3 完善 `frontend/app/screener/page.tsx`：因子條件篩選 UI + 結果表格

## 9. 警報設定頁面

- [x] 9.1 完善 `frontend/app/alerts/page.tsx`：列出現有警報清單（呼叫 `GET /api/alerts`）
- [x] 9.2 新增警報表單：選股票、條件類型（price/rsi/volume）、門檻值
- [x] 9.3 串接 `POST /api/alerts` 新增、`DELETE /api/alerts/{id}` 刪除

## 10. PWA Android 打包

- [x] 10.1 安裝 `@ducanh2912/next-pwa`（相容 Next.js 15/16）
- [x] 10.2 修改 `frontend/next.config.ts` 加入 pwa plugin 設定
- [x] 10.3 新增 `frontend/public/manifest.json`（name/icons/theme_color/display）
- [x] 10.4 新增 PWA icon（192×192 / 512×512 PNG）至 `public/icons/`
- [x] 10.5 測試：Chrome DevTools → Application → Manifest 確認無錯誤
