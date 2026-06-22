# Pine Script Alert Spec

## Purpose

提供可直接匯入 TradingView 的 Pine Script Alert 檔，與後端 webhook 完全相容。

## Requirements

### Requirement: TradingView Pine Script Alert 檔案
系統 SHALL 提供可直接匯入 TradingView 的 Pine Script `.pine` 檔，包含 Alert 條件與 JSON payload 格式，與後端 `/api/webhook/tradingview` 完全相容。

#### Scenario: Pine Script 產生正確 Alert JSON
- **WHEN** TradingView 觸發 Alert 條件
- **THEN** 推送的 JSON 包含 `symbol`、`action`、`price`、`strategy`、`target_position` 欄位，且 HMAC 密鑰欄位以佔位符標示
