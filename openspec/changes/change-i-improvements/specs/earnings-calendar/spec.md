## ADDED Requirements

### Requirement: 財報日曆資料取得與快取
系統 SHALL 每日 08:00 透過 FinMind API 取得未來 30 天的除息、除權、法說會、財報公布日，儲存於 SQLite `earnings_calendar` 表，TTL 1 天。

#### Scenario: 每日定時更新
- **WHEN** APScheduler 觸發 08:00 任務
- **THEN** 系統呼叫 FinMind 取得最新日曆資料並更新 DB

#### Scenario: 快取命中
- **WHEN** `GET /api/calendar/events?days=30` 被呼叫且 DB 資料在 TTL 內
- **THEN** 系統直接從 DB 回傳，不呼叫 FinMind

### Requirement: 財報日曆 API 端點
系統 SHALL 提供 `GET /api/calendar/events?days=N`，回傳未來 N 天（預設 30，最大 90）的日曆事件列表。

#### Scenario: 正常回傳
- **WHEN** 前端呼叫 `GET /api/calendar/events`
- **THEN** 回傳 `[{date, symbol, name, event_type, description}]` 陣列，依日期升冪排序

#### Scenario: 無資料時回傳空陣列
- **WHEN** DB 中無任何符合條件的資料
- **THEN** 回傳 `[]`，HTTP 200

### Requirement: 財報日曆前端頁面
系統 SHALL 在 `/calendar` 提供月曆視圖，以色塊區分事件類型（除息/除權/法說/財報）。

#### Scenario: 事件顯示
- **WHEN** 使用者進入 `/calendar`
- **THEN** 頁面以月曆格式顯示當月及下月事件，點擊事件顯示詳情

#### Scenario: Sidebar 連結
- **WHEN** 使用者在 Sidebar 看到「📅 財報日曆」
- **THEN** 點擊後導航至 `/calendar`
