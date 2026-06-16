## ADDED Requirements

### Requirement: SQLite DB 存放於 Windows AppData 目錄
系統 SHALL 將 SQLite 資料庫檔案存放於 `%APPDATA%\TaiwanStockRadar\data.db`，Tauri exe 啟動時自動建立目錄與檔案。

#### Scenario: 首次安裝後 DB 自動建立
- **WHEN** 使用者首次雙擊 exe
- **THEN** `%APPDATA%\TaiwanStockRadar\` 目錄自動建立，FastAPI 啟動後 `data.db` 存在

#### Scenario: Tauri 透過環境變數傳入 DB 路徑
- **WHEN** Tauri main.rs 啟動 FastAPI 程序
- **THEN** 環境變數 `DB_PATH` 設定為 AppData 下的完整 db 檔案路徑

### Requirement: 開發模式使用本地路徑
系統 SHALL 在未設定 `DB_PATH` 時使用 `backend/data/stockradar.db` 作為開發路徑，不影響已安裝的 AppData DB。

#### Scenario: 開發環境啟動 FastAPI
- **WHEN** 直接執行 `uvicorn main:app` 且未設定 `DB_PATH`
- **THEN** DB 建立於 `backend/data/stockradar.db`，與 AppData 路徑互不干擾
