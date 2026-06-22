## ADDED Requirements

### Requirement: 多空辯論機制

系統 SHALL 提供 `POST /api/analysis/debate/{symbol}` API，執行 Bull Agent vs Bear Agent 辯論，各提出 3 個論點，由 Arbiter Agent 裁決勝負並給出最終立場。

#### Scenario: 執行多空辯論

- **WHEN** 客戶端請求 `POST /api/analysis/debate/{symbol}`（可選傳入 `context` 補充資訊）
- **THEN** 系統同步執行辯論流程，Bull Agent 與 Bear Agent 各自生成 3 個論點，Arbiter Agent 評估後輸出裁決結果

#### Scenario: Bull Agent 論點格式

- **WHEN** Bull Agent 生成論點
- **THEN** 每個論點包含：`title`（論點標題）、`argument`（詳細說明，≥2 句話）、`evidence`（具體數據或事實依據）

#### Scenario: Bear Agent 論點格式

- **WHEN** Bear Agent 生成論點
- **THEN** 每個論點包含：`title`、`argument`（至少挑戰一個 Bull 論點）、`evidence`

#### Scenario: Arbiter 裁決

- **WHEN** Bull 與 Bear 各提出 3 個論點完成
- **THEN** Arbiter Agent 輸出：`verdict`（"bull"/"bear"/"neutral"）、`confidence`（60-100%）、`rationale`（裁決理由，≥3 句話）、`key_risk`（最重要的下行風險）

#### Scenario: 辯論結果 API 回應格式

- **WHEN** 辯論完成
- **THEN** 回應 JSON 包含：`symbol`、`timestamp`、`bull_arguments`（陣列）、`bear_arguments`（陣列）、`arbiter`（裁決物件）
