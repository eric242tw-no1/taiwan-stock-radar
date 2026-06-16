## 1. 建立統一 DB 模組與 SQLite Schema

- [x] 1.1 建立 `backend/db.py`：`get_conn()` 讀取 `DB_PATH` 環境變數，啟用 WAL + row_factory
- [x] 1.2 建立 `backend/data/` 目錄（加入 `.gitignore`）
- [x] 1.3 重寫 `backend/schema_sqlite.sql`：所有資料表轉換為 SQLite 語法（JSONB→TEXT、TIMESTAMPTZ→TEXT、SERIAL→INTEGER PRIMARY KEY AUTOINCREMENT、NOW()→datetime('now')）
- [x] 1.4 在 `backend/main.py` lifespan 改為執行 `schema_sqlite.sql` 初始化（取代 psycopg2 migration 函數）

## 2. 修改後端 Routers（psycopg2 → sqlite3）

- [x] 2.1 修改 `backend/routers/workflow.py`：`_get_conn()` 改為 `db.get_conn()`，SQL 語法調整
- [x] 2.2 修改 `backend/routers/journal.py`：同上
- [x] 2.3 修改 `backend/routers/analytics.py`：同上
- [x] 2.4 修改 `backend/routers/risk.py`：同上（Redis 快取邏輯保留）
- [x] 2.5 修改 `backend/routers/analysis.py`：同上
- [x] 2.6 修改 `backend/routers/reports.py`：同上
- [x] 2.7 修改 `backend/routers/strategies.py`：同上
- [x] 2.8 修改 `backend/routers/webhook.py`：同上
- [x] 2.9 修改 `backend/routers/backtest.py`：同上（若有直接 DB 操作）
- [x] 2.10 修改 `backend/routers/stock_pool.py`：同上

## 3. 修改後端 Services

- [x] 3.1 修改 `backend/services/db_migrations.py`：改用 sqlite3，確保 IF NOT EXISTS 語法正確
- [x] 3.2 修改 `backend/services/webhook_tables.py`：改用 sqlite3
- [x] 3.3 修改 `backend/services/indicator_service.py`：改用 sqlite3
- [x] 3.4 修改 `backend/services/stock_pool_service.py`：改用 sqlite3
- [x] 3.5 修改 `backend/services/portfolio_service.py`：改用 sqlite3
- [x] 3.6 修改 `backend/services/correlation_service.py`：改用 sqlite3

## 4. 修改 Health Check

- [x] 4.1 修改 `backend/routers/health.py`：移除 asyncpg，改用 sqlite3 檢查 DB 可讀寫性（SELECT 1）

## 5. 更新依賴與設定

- [x] 5.1 更新 `backend/requirements.txt`：移除 `psycopg2`、`asyncpg`
- [x] 5.2 更新 `docker-compose.yml`：移除 `postgres` service 與相關 `depends_on`
- [x] 5.3 更新 `backend/Dockerfile.prod`：移除 `libpq5`、`libpq-dev`
- [x] 5.4 更新 `start-dev.bat` 與 `啟動開發環境.bat`：移除 PostgreSQL 等待邏輯

## 6. 更新 Tauri（AppData DB 路徑注入）

- [x] 6.1 修改 `frontend/src-tauri/src/main.rs`：用 Tauri path API 取得 AppData 路徑，啟動 FastAPI 時注入 `DB_PATH` 環境變數
- [x] 6.2 確認 `Cargo.toml` 有啟用 `path-all` feature（Tauri path resolver）

## 7. 驗證

- [x] 7.1 本機啟動 FastAPI，確認 `data/stockradar.db` 自動建立且所有資料表存在
- [x] 7.2 測試 `GET /api/health` 回傳 `{"db":"ok",...}`
- [x] 7.3 測試 workflow 儲存、journal 新增、ATR 計算等需要 DB 的功能
- [ ] 7.4 重新打包 Tauri exe（`npm run tauri:build`），安裝後確認 AppData DB 建立
- [ ] 7.5 確認重複啟動 exe 不重置 DB 資料

