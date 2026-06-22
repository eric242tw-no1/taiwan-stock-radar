# Spec: Webhook

## Purpose

TradingView Webhook 整合的核心規格，定義 payload 格式與執行語意。

## Requirements

### BREAKING: Payload 格式變更
原 action-based payload（`action: "buy"|"sell"`）改為 state-based：
- 移除欄位：`action`, `quantity`
- 新增欄位：`target_position`（目標持股張數）、`secret`（HMAC）
- TV Alert message 格式需同步更新

### BREAKING: 執行語意變更
- 舊：收到 `action=buy` 直接買入指定數量
- 新：收到 `target_position`，系統自行計算 diff，執行補差
