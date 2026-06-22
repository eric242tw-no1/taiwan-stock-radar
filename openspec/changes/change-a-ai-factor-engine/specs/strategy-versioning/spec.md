## ADDED Requirements

### Requirement: Prompt 策略版本管理

系統 SHALL 提供 `strategy_versions` DB 表與對應 API，讓使用者管理不同 Prompt 配置版本，並支援版本切換（A/B 測試）。

DB Schema：
```sql
CREATE TABLE strategy_versions (
    id              SERIAL PRIMARY KEY,
    strategy_id     INTEGER REFERENCES strategies(id),
    version         VARCHAR(50) NOT NULL,
    prompt_template TEXT NOT NULL,
    parameters      JSONB DEFAULT '{}',
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### Scenario: 列出所有策略版本

- **WHEN** 客戶端請求 `GET /api/strategies/versions`（可帶 `strategy_id` 篩選）
- **THEN** 系統回傳版本清單，每筆包含 `id`、`strategy_id`、`version`、`parameters`、`is_active`、`created_at`（不回傳 `prompt_template` 全文以節省傳輸）

#### Scenario: 建立新策略版本

- **WHEN** 客戶端請求 `POST /api/strategies/versions`，body 含 `strategy_id`、`version`、`prompt_template`、`parameters`
- **THEN** 系統寫入新版本，`is_active` 預設 `false`，回傳新建版本的完整資料（含 `id`）

#### Scenario: 啟用特定版本

- **WHEN** 客戶端請求 `GET /api/strategies/versions/{id}/activate`
- **THEN** 系統將同一 `strategy_id` 下其他版本的 `is_active` 設為 `false`，目標版本設為 `true`，回傳 `{"activated": id, "strategy_id": ...}`

#### Scenario: 同策略只能有一個 active 版本

- **WHEN** 對同一 `strategy_id` 啟用新版本
- **THEN** 系統在單一 DB 交易中完成舊版停用與新版啟用，確保任何時刻最多一個 active 版本

### Requirement: Agent 使用 active 版本 Prompt

系統 SHALL 讓 multi_agent_engine 在執行時自動載入該 strategy 的 active 版本 prompt_template，若無 active 版本則使用預設 hardcode prompt。

#### Scenario: Agent 載入 active prompt

- **WHEN** Orchestrator 初始化某 Agent
- **THEN** 系統查詢 `strategy_versions` 表取得 `is_active=true` 的版本，以其 `prompt_template` 覆蓋預設 prompt
