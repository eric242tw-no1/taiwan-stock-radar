## 1. Health Check 端點

- [x] 1.1 建立 `backend/routers/health.py`：`GET /api/health` 回傳 db + redis 狀態
- [x] 1.2 在 `backend/main.py` 掛載 health router（`/api/health`）
- [x] 1.3 本機驗證：`curl http://localhost:8000/api/health` 回傳 `{"status":"ok",...}`

## 2. Docker Compose 生產配置

- [x] 2.1 建立 `docker-compose.prod.yml`：所有服務加 `restart: always` + 資源限制（memory）
- [x] 2.2 fastapi 服務加 Docker healthcheck（`curl -f /api/health`，interval 30s，retries 3）
- [x] 2.3 postgres 服務加 healthcheck（`pg_isready`，interval 10s）
- [x] 2.4 建立 `.env.prod.example`：列出所有必填環境變數（不含真實值）

## 3. Next.js 生產配置

- [x] 3.1 在 `frontend/next.config.ts` 加入 `output: 'standalone'`
- [x] 3.2 建立 `frontend/Dockerfile.prod`：multi-stage build，standalone output
- [x] 3.3 驗證 standalone build：`docker build -f frontend/Dockerfile.prod frontend/` 成功

## 4. FastAPI Docker 生產配置

- [x] 4.1 建立 `backend/Dockerfile.prod`：multi-stage，不含開發工具，用 gunicorn + uvicorn worker
- [x] 4.2 驗證 backend build：`docker build -f backend/Dockerfile.prod backend/` 成功

## 5. Nginx 配置

- [x] 5.1 建立 `nginx/nginx.conf`：upstream nextjs（3000）+ fastapi（8000），HTTP→HTTPS 跳轉
- [x] 5.2 加入靜態資源快取規則（`/_next/static/` long-term cache）
- [x] 5.3 加入 Certbot webroot 路徑（`/.well-known/acme-challenge/`）
- [x] 5.4 在 `docker-compose.prod.yml` 加入 nginx service（掛載 conf + ssl volume）

## 6. PostgreSQL 備份

- [x] 6.1 建立 `scripts/backup-db.sh`：pg_dump → `/backup/stockradar_YYYY-MM-DD.sql.gz`，保留 7 天
- [x] 6.2 在 `docker-compose.prod.yml` 加入 backup service（image: postgres，cron entrypoint）或說明 VPS cron 設定方式

## 7. GitHub Actions CI/CD

- [x] 7.1 建立 `.github/workflows/deploy.yml`：trigger on push to main
- [x] 7.2 Lint job：Python ruff + Next.js ESLint（失敗則阻擋後續）
- [x] 7.3 Build job：build fastapi + nextjs Docker images，push 到 GHCR
- [x] 7.4 Deploy job：SSH 進 VPS，`docker compose -f docker-compose.prod.yml pull && up -d`
- [x] 7.5 Deploy job 最後執行 `curl /api/health` 確認部署成功

## 8. 部署說明文件

- [x] 8.1 建立 `DEPLOY.md`：VPS 初始化步驟、Certbot 取得憑證流程、GitHub Secrets 設定清單
- [x] 8.2 在 `DEPLOY.md` 記錄 rollback 流程（git revert + push 或 VPS 直接 checkout）

## 9. 手動驗證（N/A — 本地桌面執行架構，不需 VPS）

- [N/A] 9.1 VPS 上執行 `docker compose -f docker-compose.prod.yml up -d` 確認所有服務啟動
- [N/A] 9.2 Certbot 取得 SSL 憑證，HTTPS 正常運作
- [N/A] 9.3 `GET /api/health` 回傳 200
- [N/A] 9.4 Push to main 觸發 CI/CD pipeline 全程通過
- [N/A] 9.5 手動執行備份腳本，確認 `/backup/` 產生壓縮檔
