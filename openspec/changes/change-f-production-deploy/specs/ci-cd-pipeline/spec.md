## ADDED Requirements

### Requirement: GitHub Actions 自動化部署流程
系統 SHALL 在 push to `main` 時自動執行 lint、build Docker images 並 SSH 部署至 VPS。

#### Scenario: Push to main 觸發完整 CI/CD
- **WHEN** 程式碼 push 至 `main` branch
- **THEN** GitHub Actions 依序執行：lint → build images → push to GHCR → SSH deploy

#### Scenario: Lint 失敗阻擋部署
- **WHEN** Python ruff 或 Next.js ESLint 有錯誤
- **THEN** pipeline 在 lint 階段失敗，不執行後續 build 與 deploy

#### Scenario: 部署完成後健康確認
- **WHEN** SSH deploy 執行 `docker compose up -d` 完成
- **THEN** pipeline 執行 `curl /api/health` 確認服務存活，失敗則標記 job failed
