## ADDED Requirements

### Requirement: 警報訊息自動寫入 DB
系統 SHALL 在每次 `utils/telegram.py send_message()` 執行時，同步將訊息內容、來源、時間寫入 SQLite `notifications` 表。

#### Scenario: 警報觸發後寫入
- **WHEN** 任意模組呼叫 `send_message(text, source="morning_brief")`
- **THEN** DB 新增一筆 `{message, source, created_at, is_read=0}`

#### Scenario: Telegram 發送失敗不影響寫入
- **WHEN** Telegram Bot Token 無效導致發送失敗
- **THEN** DB 仍寫入紀錄，source 標記為 `failed`

### Requirement: 通知中心 API 端點
系統 SHALL 提供 `GET /api/notifications?limit=50&offset=0` 取得歷史紀錄，以及 `PATCH /api/notifications/{id}/read` 標記已讀。

#### Scenario: 取得通知列表
- **WHEN** `GET /api/notifications` 被呼叫
- **THEN** 回傳最近 50 筆，依 `created_at` 降冪，含 `is_read` 狀態

#### Scenario: 標記已讀
- **WHEN** `PATCH /api/notifications/{id}/read`
- **THEN** 對應紀錄 `is_read` 更新為 1，回傳 `{ok: true}`

### Requirement: 每週清理舊通知
系統 SHALL 透過 APScheduler 每週日 02:00 刪除超過 1000 筆的最舊通知。

#### Scenario: 清理執行
- **WHEN** 排程觸發且 notifications 總數 > 1000
- **THEN** 刪除最舊的 (total - 1000) 筆

### Requirement: 通知中心前端頁面
系統 SHALL 在 `/notifications` 提供通知列表，顯示訊息摘要、來源、時間、已讀/未讀狀態。

#### Scenario: 列表顯示
- **WHEN** 使用者進入 `/notifications`
- **THEN** 頁面顯示歷史警報，未讀以高亮標示，點擊標記已讀

#### Scenario: Sidebar 連結含未讀數
- **WHEN** Sidebar 載入且有未讀通知
- **THEN** 「🔔 通知中心」連結旁顯示未讀數 badge
