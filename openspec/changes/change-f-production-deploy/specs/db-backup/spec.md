## ADDED Requirements

### Requirement: PostgreSQL 每日自動備份
系統 SHALL 每日凌晨 02:00 自動備份 PostgreSQL 資料庫至 `/backup/` 目錄，保留最近 7 天。

#### Scenario: 每日自動備份產生壓縮檔
- **WHEN** 系統時間到達 02:00（台灣時間）
- **THEN** 執行 `pg_dump` 並輸出 `stockradar_YYYY-MM-DD.sql.gz` 至 `/backup/`

#### Scenario: 超過 7 天的備份自動清除
- **WHEN** 備份腳本執行後 `/backup/` 中存在超過 7 個備份檔
- **THEN** 最舊的備份檔被刪除，目錄中保留最新 7 份
