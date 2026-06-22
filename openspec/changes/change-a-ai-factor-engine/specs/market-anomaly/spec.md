## MODIFIED Requirements

### Requirement: 市場異常偵測整合 factor_engine

市場異常偵測代理 SHALL 透過 `factor_engine` 取得技術指標，不再於 `market_anomaly_agent.py` 內部自行計算，以確保指標計算邏輯一致。

#### Scenario: 使用 factor_engine 計算 RSI 判斷超買超賣

- **WHEN** market_anomaly_agent 需要判斷個股 RSI 狀態
- **THEN** agent 呼叫 `factor_engine.technical.compute(symbol, ohlcv_df)` 取得 RSI 值，不重複實作計算邏輯

#### Scenario: FactorBundle 傳入 anomaly 判斷流程

- **WHEN** market_anomaly_agent 偵測到異常候選股票
- **THEN** agent 取得該股票的 `FactorBundle`，以統一格式記錄於異常事件中（`factor_snapshot` 欄位）
