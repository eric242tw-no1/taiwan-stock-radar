## ADDED Requirements

### Requirement: 生產用 Docker Compose 配置
系統 SHALL 提供 `docker-compose.prod.yml`，包含所有服務（postgres、redis、fastapi、celery、nextjs）的生產級設定，含 restart policy、資源限制與 healthcheck。

#### Scenario: 所有服務隨機器重啟自動恢復
- **WHEN** VPS 重新開機
- **THEN** 所有 Docker 服務在 Docker daemon 啟動後自動恢復運行（`restart: always`）

#### Scenario: 服務記憶體限制防止 OOM
- **WHEN** 任一服務記憶體用量超過限制
- **THEN** Docker 終止該服務並自動重啟，不影響其他服務

#### Scenario: Healthcheck 偵測服務存活
- **WHEN** Docker compose 啟動後
- **THEN** fastapi 服務每 30 秒執行 `GET /api/health` 確認存活；postgres 每 10 秒執行 `pg_isready`
