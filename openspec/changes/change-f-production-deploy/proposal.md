## Why

所有功能 Sprint（Phase 0–5）已完成，系統目前只能在本機開發環境運行。需要建立生產級部署配置，讓系統可以穩定對外服務，並具備基本的可觀測性與自動化部署能力。

## What Changes

- 新增 `docker-compose.prod.yml`：生產用 compose，含資源限制、restart policy、secrets 管理
- 新增 Nginx 反向代理設定：SSL 終止、靜態資源 cache、upstream FastAPI
- Next.js 靜態輸出或獨立模式（`output: standalone`）配置
- 環境變數與 secrets 管理：`.env.prod` 範本 + Docker secrets 支援
- PostgreSQL 生產備份腳本（pg_dump 每日 cron）
- GitHub Actions CI/CD pipeline：lint → test → build → deploy
- 健康檢查端點（`/api/health`）與 Docker healthcheck 設定
- Nginx SSL 設定（Let's Encrypt / Certbot 自動續期）

## Capabilities

### New Capabilities
- `production-compose`: Docker Compose 生產配置，含所有服務的資源限制與健康檢查
- `nginx-ssl`: Nginx 反向代理 + SSL 終止 + 靜態資源快取
- `ci-cd-pipeline`: GitHub Actions 自動化 lint/test/build/deploy 流程
- `db-backup`: PostgreSQL 每日備份腳本與 cron 設定
- `health-check`: FastAPI `/api/health` 端點 + Docker healthcheck

### Modified Capabilities
- `docker-compose` 現有開發用 compose 不變，新增 prod 版本

## Impact

- **新增檔案**：`docker-compose.prod.yml`、`nginx/nginx.conf`、`nginx/ssl/`、`.github/workflows/deploy.yml`、`scripts/backup-db.sh`、`backend/routers/health.py`
- **修改檔案**：`frontend/next.config.ts`（standalone output）、`backend/main.py`（掛載 health router）、`docker-compose.yml`（加 healthcheck）
- **依賴新增**：Nginx Docker image、Certbot、GitHub Actions runners
- **API 新增**：`GET /api/health` → `{"status":"ok","version":"...","db":"ok","redis":"ok"}`
