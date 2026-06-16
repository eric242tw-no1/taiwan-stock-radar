## Context

目前架構以 PostgreSQL（Docker 容器）作為主要資料庫，所有 backend router 使用 `psycopg2` 建立連線。桌面 app（Tauri exe）啟動時需要 Docker Desktop 先就緒、postgres 容器健康，才能進行任何資料庫操作。本次遷移將資料庫換成 SQLite，使 app 完全脫離 Docker 資料庫依賴。

**現有 DB 相關檔案（需修改）：**
- `backend/routers/`：analysis, analytics, journal, reports, risk, strategies, webhook, workflow（各自有 `_get_conn()`）
- `backend/services/db_migrations.py`、`webhook_tables.py`、`indicator_service.py` 等
- `backend/schema.sql`：PostgreSQL DDL

## Goals / Non-Goals

**Goals:**
- 所有資料庫操作改用 Python 內建 `sqlite3`
- SQLite DB 檔案存放於 `%APPDATA%\TaiwanStockRadar\data.db`
- FastAPI 啟動時自動建立目錄與 DB（若不存在）
- Tauri exe 啟動 FastAPI 時透過 `DB_PATH` 環境變數傳入 DB 路徑
- `docker-compose.yml` 移除 postgres service
- 保留 Redis（Celery 仍需要）

**Non-Goals:**
- 現有 PostgreSQL 資料自動遷移（開發環境重新初始化即可）
- 支援多使用者並發寫入（本 app 為單人桌面工具，SQLite WAL 模式已足夠）
- 更換 ORM（維持原有 raw SQL 風格）

## Decisions

### 1. DB 路徑由環境變數 `DB_PATH` 控制

**選擇**：`os.getenv("DB_PATH", default_path)` 讀取路徑，FastAPI 啟動時由 Tauri 或 .bat 注入。

**原因**：彈性最高，開發時可指定測試路徑，生產時由 Tauri 傳入 AppData 路徑。

**Default 路徑**（開發用）：`./data/stockradar.db`（backend 目錄下）

### 2. 統一 `get_db_conn()` 工具函數

**選擇**：在 `backend/db.py` 建立單一 `get_conn()` 函數，所有 router import 它，取代各自的 `_get_conn()`。

**原因**：避免 15 個檔案各自重複 DB 路徑邏輯，遷移風險集中在一個地方。

```python
# backend/db.py
import sqlite3, os

DB_PATH = os.getenv("DB_PATH", "./data/stockradar.db")

def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
```

### 3. Schema 型別對應

| PostgreSQL | SQLite |
|---|---|
| `SERIAL PRIMARY KEY` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| `JSONB` | `TEXT`（JSON 字串） |
| `TIMESTAMPTZ` / `TIMESTAMP` | `TEXT`（ISO 8601 字串） |
| `NOW()` | `datetime('now')` |
| `BOOLEAN` | `INTEGER`（0/1） |
| `NUMERIC` | `REAL` |
| `VARCHAR(n)` | `TEXT` |

### 4. Schema 初始化策略

**選擇**：FastAPI lifespan 啟動時執行 `backend/schema_sqlite.sql`（`CREATE TABLE IF NOT EXISTS`），不使用 migration 框架。

**原因**：app 為單機工具，不需要版本化 migration；IF NOT EXISTS 保證冪等性。

### 5. Celery / Redis 保留

**選擇**：維持 Redis in Docker + Celery，不改動。

**原因**：Celery 只需改 `REDIS_URL` 環境變數，遷移範圍不必擴大到非同步任務架構。

### 6. Tauri 注入 DB_PATH

`main.rs` 用 `tauri::api::path::app_data_dir()` 取得 AppData 路徑，傳給 FastAPI：

```rust
let db_path = app.path_resolver()
    .app_data_dir()
    .map(|p| p.join("stockradar.db"))
    .unwrap_or_else(|| PathBuf::from("./data/stockradar.db"));

// 啟動 FastAPI 時加入 DB_PATH env
Command::new("python")
    .env("DB_PATH", db_path.to_str().unwrap_or(""))
    ...
```

## Risks / Trade-offs

- **SQLite 並發寫入限制** → WAL 模式下多 reader + 單 writer 已足夠本機單人使用
- **JSON 欄位失去型別索引** → 查詢效能略降，但資料量小（本地用）影響不大
- **現有資料遺失** → 開發環境重新初始化；生產部署前需告知用戶
- **15 個 router 需修改** → 統一 `db.py` 降低重複修改風險，但仍需逐一驗證

## Migration Plan

1. 建立 `backend/db.py`（統一連線函數）
2. 重寫 `backend/schema_sqlite.sql`
3. 逐一修改各 router（psycopg2 → sqlite3，SQL 語法調整）
4. 修改 `backend/services/` 相關檔案
5. 修改 `backend/main.py` lifespan（載入 SQLite schema）
6. 更新 `backend/requirements.txt`（移除 psycopg2、asyncpg）
7. 更新 `docker-compose.yml`（移除 postgres service）
8. 更新 Tauri `main.rs`（注入 DB_PATH）
9. 更新 `.bat` 啟動腳本（移除 postgres 等待邏輯）
10. 本機驗證：所有 API 端點正常運作
