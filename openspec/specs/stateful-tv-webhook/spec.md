# Spec: Stateful TradingView Webhook

## Purpose

以 target_position（目標持倉張數）取代 action-based 指令，讓系統自行計算差值並執行補倉/減倉，同時加入 HMAC 驗證、Redis 去重與 AI 審查。

## Requirements

### Webhook Payload Schema
- 系統接受 `POST /api/webhook/tradingview`，payload 格式：
  ```json
  {
    "secret": "<hmac_secret>",
    "symbol": "2330",
    "target_position": 1000,
    "strategy_id": "momentum_v2",
    "price_close": 850.0,
    "timestamp": "2026-06-13T09:00:00Z"
  }
  ```
- `target_position` 正數 = 多單張數，0 = 清倉，負數 = 空單（台股通常 0 或正值）

### HMAC 驗證
- 使用 `hmac.compare_digest(secret, env.TV_WEBHOOK_SECRET)` 驗證
- 驗證失敗回傳 `403 Forbidden`，不執行任何後續邏輯

### Redis Dedup
- key：`tv_signal:{strategy_id}:{symbol}:{timestamp // 60}`，TTL 60s
- 重複訊號回傳 `200 OK`（body: `{"status": "deduped"}`），寫入 `tv_signals` 表 `status=deduped`

### 持倉 Diff 計算
- 查詢 `YuantaBroker.get_position(symbol)` 取得當前實際持倉
- `diff = target_position - actual_position`
- `diff > 0` → 買入；`diff < 0` → 賣出；`diff == 0` → 無操作

### Devil's Advocate 審查
- 呼叫 AI 審查，timeout 10s
- `confidence < 0.6` → `status=rejected_by_ai`，不執行
- timeout → `status=ai_timeout`，bypass 審查，執行訂單

### 訂單執行與記錄
- 呼叫 `YuantaBroker.place_order(symbol, diff, price)`
- 寫入 `tv_signals`：signal log（含 dedup_key、target_position、actual_position、diff、status、executed_at）
- 寫入 `orders`：訂單記錄

### Legacy 過渡
- 舊 endpoint 保留為 `/api/webhook/tradingview-legacy`，1 週後移除
