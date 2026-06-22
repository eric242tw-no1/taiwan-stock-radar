## Context

系統目前以開發模式運行：Next.js `npm run dev`、FastAPI `uvicorn --reload`、Docker Compose 含 PostgreSQL + Redis + Celery。Phase 0–5 所有功能已完成，需要從「本機可用」升級到「生產可部署」狀態。

部署目標：單台 VPS（Linux，Ubuntu 22.04），Nginx 作前端反代，Docker Compose 管理所有後端服務，Let's Encrypt 提供 SSL。

## Goals / Non-Goals

**Goals:**
- 生產用 docker-compose.prod.yml（資源限制、restart always、secrets）
- Nginx + SSL 終止，前端靜態輸出或 standalone 模式
- GitHub Actions CI/CD：push to main → build → deploy（ssh remote）
- PostgreSQL 每日備份至本機 `/backup/` 目錄
- FastAPI `/api/health` 端點，Docker healthcheck 整合
- `.env.prod.example` 範本，正式機不 commit secrets

**Non-Goals:**
- Kubernetes / 雲端 managed services（AWS RDS、Cloud Run 等）
- 多機水平擴展
- 付費監控服務（Datadog、New Relic）
- 藍綠部署、零停機滾動更新

## Decisions

**D1: Next.js 使用 standalone output**
- `output: 'standalone'` 讓 Next.js 打包成自包含 Node server，Docker image 大幅縮小
- 替代方案：`next export`（靜態）— 但本專案有 SSR/rewrites，不適用

**D2: Nginx 作為唯一對外入口**
- 所有流量進 Nginx（80/443），再分發至 Next.js（3000）和 FastAPI（8000）
- 靜態資源（`/_next/static/`）直接由 Nginx serve，減少 Node 負擔
- TradingView Webhook（`/api/webhook/tradingview`）需要設定較大 body size（`client_max_body_size 1m`）

**D3: GitHub Actions SSH deploy**
- CI build Docker images，push 到 GitHub Container Registry（ghcr.io）
- deploy job SSH 進 VPS，`docker compose pull && docker compose up -d`
- 替代方案：自建 registry — 維護成本高，GHCR 免費且與 Actions 整合佳

**D4: Secrets 管理用 .env.prod + GitHub Secrets**
- VPS 上放 `.env.prod`（不進版控），Actions 透過 `${{ secrets.xxx }}` 注入 deploy script
- 不使用 Docker Swarm secrets（過重）或 Vault（overkill）

**D5: 備份策略 — pg_dump + cron**
- 每日 02:00 在 postgres container 內執行 `pg_dump`，輸出壓縮 `.sql.gz` 至 volume
- 保留最近 7 天，第 8 天覆蓋最舊的
- 替代方案：WAL archiving — 複雜度高，對本專案規模不必要

## Risks / Trade-offs

- [風險] Next.js standalone 模式需驗證 rewrite proxy 仍可用 → 部署後實測 `/api/*` 路由
- [風險] Celery worker 在生產 compose 的記憶體限制可能影響長時間 AI 任務 → 初期設 512MB，觀察後調整
- [風險] Let's Encrypt 需要域名 A record 指向 VPS → 部署前需先設定 DNS，無法在本機測試
- [取捨] GitHub Actions SSH deploy 為 push-to-deploy，沒有 rollback 機制 → 靠 git revert + 重新 push 解決

## Migration Plan

1. VPS 準備：安裝 Docker、Docker Compose v2、Nginx、Certbot
2. Clone repo，建立 `.env.prod`（複製 `.env.prod.example` 填值）
3. `docker compose -f docker-compose.prod.yml up -d` 啟動所有服務
4. Certbot 取得 SSL 憑證，更新 `nginx/nginx.conf`
5. 設定 GitHub Secrets（VPS_HOST、VPS_USER、SSH_PRIVATE_KEY 等）
6. Push to main 觸發 CI/CD 驗證 pipeline 正常

**Rollback**: `git revert` + push → CI/CD 重新部署舊版；或直接在 VPS `git checkout <hash> && docker compose up -d`

## Open Questions

- VPS 規格？（建議最低 2 vCPU / 4GB RAM，Celery + AI 任務較吃記憶體）
- 域名是否已有？Certbot 需要 HTTP-01 challenge
- 備份是否需要異地（S3/rclone）？目前設計只備份至本機
