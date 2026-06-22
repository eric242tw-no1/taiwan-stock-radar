## ADDED Requirements

### Requirement: 兩段式下單確認彈窗
系統 SHALL 在前端執行任何下單操作前顯示確認 Modal，列出股票代號、名稱、方向、數量、預估價格、停損位，使用者明確確認後才送出 API。

#### Scenario: 點擊下單按鈕彈出確認 Modal
- **WHEN** 使用者在任何頁面點擊下單按鈕
- **THEN** 彈出 OrderConfirmModal，顯示完整下單資訊，包含「確認下單」與「取消」兩個按鈕

#### Scenario: 確認後送出下單
- **WHEN** 使用者點擊「確認下單」
- **THEN** Modal 關閉，系統送出 POST /api/orders/place，顯示成功/失敗 toast

#### Scenario: 取消不送出任何請求
- **WHEN** 使用者點擊「取消」或按 ESC
- **THEN** Modal 關閉，不送出任何 API 請求

### Requirement: 環境徽章顯示
系統 SHALL 在頁面右上角顯示環境徽章：模擬環境顯示黃色「模擬」，正式環境顯示紅色「正式」。

#### Scenario: 模擬環境顯示黃色徽章
- **WHEN** 環境變數 `TRADING_ENV=simulation`（或未設定）
- **THEN** Sidebar 或 Header 顯示黃底黑字「模擬」徽章

#### Scenario: 正式環境顯示紅色徽章
- **WHEN** 環境變數 `TRADING_ENV=live`
- **THEN** 顯示紅底白字「正式」徽章，OrderConfirmModal 標題加紅色警告框
