## ADDED Requirements

### Requirement: 統一 SQLite 連線模組
系統 SHALL 提供 `backend/db.py` 作為唯一的資料庫連線入口，所有 router 與 service 透過此模組取得 SQLite 連線，不得直接使用 psycopg2。

#### Scenario: 連線成功回傳 sqlite3.Connection
- **WHEN** 任意 router 呼叫 `db.get_conn()`
- **THEN** 回傳啟用 WAL 模式、row_factory 為 sqlite3.Row 的連線物件

#### Scenario: DB 路徑由環境變數控制
- **WHEN** 環境變數 `DB_PATH` 已設定
- **THEN** `get_conn()` 使用該路徑建立連線

#### Scenario: 未設定環境變數時使用預設路徑
- **WHEN** 環境變數 `DB_PATH` 未設定
- **THEN** `get_conn()` 使用 `./data/stockradar.db` 作為預設路徑

### Requirement: SQLite Schema 初始化
系統 SHALL 在 FastAPI lifespan 啟動時執行 `backend/schema_sqlite.sql`，使用 `CREATE TABLE IF NOT EXISTS` 確保所有資料表存在。

#### Scenario: 首次啟動自動建立所有資料表
- **WHEN** SQLite DB 檔案不存在或為空
- **THEN** FastAPI 啟動後所有資料表已建立，可正常寫入

#### Scenario: 重複啟動不重置資料
- **WHEN** SQLite DB 檔案已存在且含有資料
- **THEN** FastAPI 啟動後現有資料保留不變

### Requirement: PostgreSQL 型別對應
系統 SHALL 將所有 PostgreSQL 專有型別對應為 SQLite 相容型別：`JSONB`→`TEXT`、`TIMESTAMPTZ`→`TEXT`、`SERIAL`→`INTEGER PRIMARY KEY AUTOINCREMENT`、`NOW()`→`datetime('now')`。

#### Scenario: JSON 資料正確存取
- **WHEN** router 寫入 JSON 資料（如 nodes_json、report_json）
- **THEN** 資料以 JSON 字串形式存入 TEXT 欄位，讀取時可正確 parse
