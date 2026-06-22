## ADDED Requirements

### Requirement: FastAPI 健康檢查端點
系統 SHALL 提供 `GET /api/health` 端點，回傳服務、資料庫與 Redis 的存活狀態。

#### Scenario: 所有依賴正常時回傳 200
- **WHEN** PostgreSQL 與 Redis 皆可連線
- **THEN** 端點回傳 HTTP 200，body 為 `{"status":"ok","db":"ok","redis":"ok","version":"<git-sha>"}`

#### Scenario: 資料庫異常時回傳 503
- **WHEN** PostgreSQL 連線失敗
- **THEN** 端點回傳 HTTP 503，body 含 `"db":"error"` 與錯誤描述

#### Scenario: Docker healthcheck 使用此端點
- **WHEN** Docker 執行 container healthcheck
- **THEN** healthcheck 指令為 `curl -f http://localhost:8000/api/health`；連續 3 次失敗則標記 unhealthy
