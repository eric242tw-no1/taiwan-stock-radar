# StopLossGuard 雙層完整版 Spec

## Purpose

實作雙層停損機制，確保停損在任何情況下必然執行。

## Requirements

### Requirement: StopLossGuard 雙層完整版
系統 SHALL 實作完整 `StopLossGuard` 類別，包含 Layer 1（下單同時委託停損單）與 Layer 2（每分鐘輪詢備援），確保停損必然執行。

#### Scenario: Layer 1 委託停損單隨進場單同時送出
- **WHEN** 執行市價買單
- **THEN** 同步送出停損委託單（stop order），停損價 = 買入價 × (1 - stop_pct)

#### Scenario: Layer 1 委託失敗時 Layer 2 接管
- **WHEN** 停損委託單因券商拒絕或網路問題失敗
- **THEN** Layer 2 每分鐘輪詢當前價格，當 current_price ≤ stop_price 時執行市價賣單

#### Scenario: 停損觸發後推播 Telegram 通知
- **WHEN** Layer 1 或 Layer 2 觸發停損執行
- **THEN** 系統推播 Telegram 訊息：「⚠️ 停損觸發：{symbol} 賣出 {quantity}股 @{price}」
