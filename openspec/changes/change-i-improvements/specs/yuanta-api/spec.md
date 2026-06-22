## ADDED Requirements

### Requirement: 元大證券 Open API 認證整合
系統 SHALL 使用元大 Open API 的 OAuth 2.0 / API Key 認證機制，透過 `YUANTA_BASE_URL`、`YUANTA_API_KEY`、`YUANTA_ACCOUNT` 環境變數完成連線設定。

#### Scenario: 認證成功
- **WHEN** 環境變數設定正確且呼叫 `GET /balance`
- **THEN** `YuantaBroker` 成功取得帳戶餘額，無拋出例外

#### Scenario: 認證失敗容錯
- **WHEN** `YUANTA_API_KEY` 無效
- **THEN** 拋出 `BrokerConnectionError`，記錄 WARNING log，不影響其他服務

### Requirement: 模擬模式與正式模式切換
系統 SHALL 透過 `YUANTA_SIMULATION=true/false` 環境變數控制下單模式；模擬模式下單不送出真實委託。

#### Scenario: 模擬模式下單
- **WHEN** `YUANTA_SIMULATION=true` 且呼叫 `place_order()`
- **THEN** 回傳模擬成功回應 `{order_id: "SIM-xxx", status: "simulated"}`，不呼叫元大 API

#### Scenario: 正式模式下單
- **WHEN** `YUANTA_SIMULATION=false` 且呼叫 `place_order(symbol, "buy", "limit", qty, price)`
- **THEN** 送出真實委託至元大 API，回傳 `{order_id, status, filled_qty}`

### Requirement: 持倉查詢正確對應台股格式
系統 SHALL 在 `get_positions()` 將元大 API 回傳的股數（shares）轉換為張數（lots = shares / 1000）。

#### Scenario: 持倉格式轉換
- **WHEN** 呼叫 `get_positions()`
- **THEN** 每筆持倉包含 `{symbol, qty_lots, avg_price, current_price, pnl_twd}`

### Requirement: 委託錯誤統一回報
系統 SHALL 在 `place_order` / `cancel_order` 遭遇元大 API 錯誤時，拋出包含原始錯誤碼的 `BrokerOrderError`。

#### Scenario: 下單被拒
- **WHEN** 元大 API 回傳 4xx（如資金不足）
- **THEN** 拋出 `BrokerOrderError(code, message)`，上層 RiskManager 捕獲並記錄
