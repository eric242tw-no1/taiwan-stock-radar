# Spec: strategy-version-page

## Purpose

策略版本管理頁 — 提供 `/strategy` 頁面讓使用者瀏覽、新增策略版本（prompt template），並在 Sidebar 中整合導覽連結。

## Requirements

### Requirement: 策略版本列表頁
系統 SHALL 提供 `/strategy` 頁面，呼叫 `GET /api/strategies/versions` 顯示所有策略版本。

#### Scenario: 載入策略版本列表
- **WHEN** 使用者進入 `/strategy` 頁面
- **THEN** 系統顯示所有策略版本卡片，含：版本名稱、建立時間、是否為 active 版本

#### Scenario: 空列表
- **WHEN** 無任何策略版本
- **THEN** 系統顯示「尚無策略版本，請新增第一個版本」提示

### Requirement: 新增策略版本
系統 SHALL 提供表單，讓使用者填寫版本名稱與 prompt template 並呼叫 `POST /api/strategies/versions` 儲存。

#### Scenario: 新增策略版本成功
- **WHEN** 使用者填寫版本名稱（非空）與 prompt template 並送出
- **THEN** 系統呼叫 POST API，成功後將新版本加入列表

#### Scenario: 版本名稱為空時不允許送出
- **WHEN** 使用者未填寫版本名稱即嘗試送出
- **THEN** 系統顯示欄位錯誤提示，不發出 API 請求

#### Scenario: 新增失敗
- **WHEN** POST API 回應非 200
- **THEN** 系統顯示「儲存失敗，請重試」錯誤訊息

### Requirement: Sidebar 新增策略版本連結
Sidebar SHALL 在現有導覽項目中新增「📋 策略版本」連結，指向 `/strategy`。

#### Scenario: Sidebar 顯示策略版本連結
- **WHEN** 使用者查看 Sidebar
- **THEN** 「策略版本」連結可見且點擊後導向 `/strategy` 頁面
