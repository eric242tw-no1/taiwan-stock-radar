# Telegram 互動按鈕 Spec

## Purpose

在 TradingView webhook 觸發下單流程時，透過 Telegram Inline Keyboard 讓使用者確認後才實際下單。

## Requirements

### Requirement: Telegram Inline Keyboard 互動按鈕
系統 SHALL 在 TradingView webhook 觸發下單流程時，先推播含互動按鈕的 Telegram 訊息，等待使用者確認後才實際下單。

#### Scenario: 推播含三個按鈕的確認訊息
- **WHEN** 系統收到 webhook 信號並完成 AI 分析
- **THEN** Telegram Bot 推播訊息包含 [✅ 確認下單] [❌ 取消] [🔍 查看分析] 三個 inline keyboard 按鈕

#### Scenario: 使用者點擊確認下單
- **WHEN** 使用者點擊 [✅ 確認下單] 按鈕
- **THEN** 系統執行下單，更新 Telegram 訊息顯示「已下單：{symbol} {quantity}股 @{price}」

#### Scenario: 使用者點擊取消
- **WHEN** 使用者點擊 [❌ 取消] 按鈕
- **THEN** 系統取消下單，更新 Telegram 訊息顯示「已取消」，tv_signals 狀態更新為 cancelled

#### Scenario: 使用者點擊查看分析
- **WHEN** 使用者點擊 [🔍 查看分析] 按鈕
- **THEN** Telegram Bot 回傳 AI 分析摘要（UZI 評分 + 多空辯論結論），並保留原按鈕供後續操作

#### Scenario: 60 秒內無回應自動取消
- **WHEN** 推播確認訊息後超過 60 秒無使用者操作
- **THEN** 系統自動取消，更新 Telegram 訊息顯示「已逾時自動取消」
