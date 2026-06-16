## Why

目前桌面 app 依賴 Docker 運行 PostgreSQL，導致啟動繁瑣、資源佔用高，且與本地 `stockradar-pg` 容器產生 port 衝突。對於單人本地使用的桌面工具，SQLite 是更合適的選擇，可完全消除資料庫的 Docker 依賴，讓 exe 真正做到一鍵啟動。

## What Changes

- **BREAKING** 將所有後端資料庫驅動從 `psycopg2` 換成 Python 內建 `sqlite3`
- SQLite 資料庫檔案存放於 `%APPDATA%\TaiwanStockRadar\data.db`（Windows AppData）
- 重寫 `backend/schema.sql` 為 SQLite 相容語法（移除 JSONB、TIMESTAMPTZ、SERIAL 等 PG 專有型別）
- 所有 router 的 `_get_conn()` 改為回傳 SQLite 連線
- 移除 `docker-compose.yml` 的 `postgres` service
- Celery / Redis：保留 Redis in Docker 供 Celery 使用；若 Redis 不可用則任務改為同步執行（fallback）
- `backend/Dockerfile.prod` 移除 `libpq-dev` 依賴
- Tauri `main.rs` 啟動 FastAPI 時透過環境變數傳入 SQLite DB 路徑
- 移除 `asyncpg` 依賴（health router 改用 sqlite3 檢查）

## Capabilities

### New Capabilities

- `sqlite-db-layer`：以 SQLite 取代 PostgreSQL，提供本地檔案型資料庫層，包含連線管理、schema 初始化、路徑設定
- `appdata-storage`：資料庫及應用資料存放於 Windows AppData 標準目錄，支援 Tauri 啟動時自動建立目錄與 DB 檔案

### Modified Capabilities

- `health-check`：`GET /api/health` 改為檢查 SQLite 檔案可讀寫性，而非 PostgreSQL 連線狀態

## Impact

- **後端**：所有 `routers/` 與 `services/` 中使用 psycopg2 的檔案（約 15 個）
- **依賴**：移除 `psycopg2`、`asyncpg`；無需新增套件（sqlite3 為 Python 內建）
- **Docker**：`docker-compose.yml` 移除 postgres service，只保留 redis、fastapi、celery
- **Tauri**：`main.rs` 新增環境變數注入邏輯
- **Schema**：`backend/schema.sql` 完整重寫
- **資料遷移**：現有 PostgreSQL 資料不自動遷移（本地開發環境可重新初始化）
