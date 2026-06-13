## Context

現有 `POST /api/webhook/tradingview` 接收買賣動作指令，中途斷線會導致持倉與訊號不同步。`stop_loss_guard.py` 包含風控邏輯，但無法被 Webhook 或其他 Agent 複用。Yuanta portfolio 頁面使用 hardcoded demo 資料。

## Goals / Non-Goals

**Goals:**
- Webhook 改為 state-based：接收 `target_position`，查詢實際持倉，計算 diff，執行補差
- HMAC 簽名驗證防止偽造訊號
- Redis dedup 防止重複執行
- RiskManager 獨立服務，可被任何模組呼叫
- Yuanta 持倉頁面顯示真實資料

**Non-Goals:**
- 多券商支援（Phase 3）
- 自動切換 simulation→live（需手動設定 `YUANTA_LIVE=true`）
- TradingView Pine Script 自動同步

## Decisions

**D1: State-based vs action-based webhook**
選 state-based。TV 傳送 `target_position`（目標持股張數），系統查詢實際持倉，計算 diff，只執行差額。斷線重連後任何時刻收到訊號都能自動同步。

**D2: HMAC 驗證**
使用 Python stdlib `hmac.compare_digest`。Secret 放在 `.env` 的 `TV_WEBHOOK_SECRET`。TV Alert message 格式：`{"secret":"{{strategy.alert_message}}", ...}`。不使用 IP allowlist（TV IP 不固定）。

**D3: Redis dedup key 設計**
`tv_signal:{strategy_id}:{symbol}:{ts_bucket}` 其中 `ts_bucket = timestamp // 60`（60 秒桶）。TTL 60s。被 dedup 的訊號寫入 `tv_signals` 表 `status=deduped`，不靜默丟棄。

**D4: Devil's Advocate 審查**
每筆訊號執行前呼叫 `ai_engine.py` 的 devil_advocate 方法，若 confidence < 0.6 則拒絕執行，記錄 `status=rejected_by_ai`。超時 10s 則 bypass（記錄 `status=ai_timeout`）。

**D5: RiskManager 解耦**
新增 `backend/services/risk_manager.py`，`RiskDecision` dataclass 輸出。`stop_loss_guard.py` 改為呼叫 RiskManager，不重複邏輯。

**D6: Yuanta WebSocket 更新頻率**
30 秒 polling（非 push），因 Yuanta broker SDK 目前不支援 push event。前端用 `setInterval` 呼叫 `GET /api/portfolio/positions`，由 WebSocket bridge 推送更新。

## Risks / Trade-offs

- [TV webhook secret 洩漏] → 定期 rotate secret；secret 不寫進 git
- [Celery 未到位前 Devil's Advocate 阻塞 webhook] → 設定 10s hard timeout bypass
- [Yuanta simulation→live 切換後誤下真實訂單] → `YUANTA_LIVE` 預設 false；live 模式需要第二層確認

## Migration Plan

1. 部署新 webhook endpoint（保留舊 endpoint 為 `/api/webhook/tradingview-legacy` 過渡期 1 週）
2. 更新 TradingView 所有 Alert 的 message 格式加入 HMAC secret
3. 執行 DB migration 新增 tv_signals、orders、account_snapshots
4. 確認 Redis dedup 正常後關閉 legacy endpoint
5. `YUANTA_LIVE=false` 全程，real data 測試通過後再評估切換
