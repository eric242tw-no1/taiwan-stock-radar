## ADDED Requirements

### Requirement: 使用者可在股票分析頁計算 ATR 動態停損
系統 SHALL 在 `/stock` 頁面提供「ATR 停損計算器」按鈕，點擊後開啟 Modal。使用者輸入買入價與 ATR 倍數（預設 2.5x），系統呼叫 `GET /api/risk/atr-stop/{symbol}?entry_price=X&multiplier=2.5`，後端從歷史資料計算 ATR 後回傳停損資訊。

#### Scenario: 開啟計算器 Modal
- **WHEN** 使用者在 `/stock?symbol=2330` 頁面點擊「ATR 停損計算器」
- **THEN** 系統開啟 Modal，股票代號預填為 2330

#### Scenario: 計算停損價
- **WHEN** 使用者輸入買入價 500、ATR 倍數 2.5 並點擊「計算」
- **THEN** 系統呼叫後端 API，顯示：ATR 值、停損價（買入價 - ATR × 倍數）、停損金額（元）、停損比例（%）

#### Scenario: 後端 API 快取命中
- **WHEN** 同一股票在 5 分鐘內再次查詢
- **THEN** 後端從 Redis 快取直接回傳 ATR，回應時間 < 100ms

### Requirement: 系統依風險比例建議張數
後端 SHALL 接受可選參數 `capital`（總資金）與 `risk_pct`（單筆風險比例，預設 2%），計算建議交易張數與最大投入金額。

#### Scenario: 帶資金參數計算張數
- **WHEN** 使用者額外輸入總資金 1,000,000 元、風險比例 2%
- **THEN** 系統顯示：可承受風險金額（20,000）、建議張數（floor(風險金額 / 停損金額 / 1000)）、最大投入金額

#### Scenario: ATR 資料不足
- **WHEN** 股票歷史資料少於 14 個交易日
- **THEN** API 回傳 422，Modal 顯示「歷史資料不足，無法計算 ATR」
