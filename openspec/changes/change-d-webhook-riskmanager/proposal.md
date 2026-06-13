## Why

現有 TradingView Webhook 是 action-based（買入/賣出指令），斷線後訊號遺失會導致持倉錯亂且無法自動修復。RiskManager 邏輯分散耦合在 stop_loss_guard 內，無法跨模組複用。Yuanta 持倉頁面顯示 demo 假資料，無法反映真實帳戶狀況。

## What Changes

- **BREAKING** 重寫 `POST /api/webhook/tradingview`：從 action-based 改為 state-based（接收 `target_position`，計算 diff 後執行）
- 新增 HMAC 簽名驗證，拒絕未簽名請求
- Redis dedup key：`tv_signal:{strategy_id}:{symbol}:{timestamp_bucket_60s}`，TTL 60s，所有被 dedup 的訊號記錄 `status=deduped`
- Devil's Advocate AI 審查每筆訊號再執行
- 新增獨立 `backend/services/risk_manager.py`（解耦自 stop_loss_guard）
- 新增 `GET /api/risk/assessment/{symbol}` endpoint
- Yuanta 持倉頁面改接真實 API，WebSocket 30 秒更新一次
- 新增 DB tables：`tv_signals`、`orders`、`account_snapshots`

## Capabilities

### New Capabilities

- `stateful-tv-webhook`: 接收 TradingView target_position，計算持倉 diff，HMAC 驗證，Redis dedup，Devil's Advocate 審查，執行下單並記錄
- `risk-manager`: 獨立風控服務，提供倉位計算、最大回撤檢查、相關性風險評估，可被任何 Agent 或 Webhook 呼叫
- `yuanta-portfolio`: 真實 Yuanta 帳戶持倉頁面，含 WebSocket 即時更新、P&L、保證金使用率

### Modified Capabilities

- `webhook`: Webhook endpoint 行為從 action-based 改為 state-based（破壞性變更）

## Impact

- **後端**：`backend/routers/webhook.py`（重寫）、`backend/agents/stop_loss_guard.py`（解耦）、新增 `backend/services/risk_manager.py`
- **前端**：`frontend/app/portfolio/page.tsx`（接真實 API）
- **DB**：新增 3 張 table（tv_signals、orders、account_snapshots）
- **依賴**：Redis（已有）、Yuanta broker SDK（已有 simulation mode）、hmac（Python stdlib）
- **破壞性**：TV Alert 的 payload 格式必須同步更新（需在 TradingView 策略設定中修改 alert message 格式）
