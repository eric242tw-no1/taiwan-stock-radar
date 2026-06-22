## MODIFIED Requirements

### Requirement: 晨報整合 multi-agent-engine 深度分析

晨報代理 SHALL 在產生重點個股分析時，選擇性呼叫 `multi_agent_engine` 取得多 Agent 綜合建議，以提升分析深度；此功能為選配，可透過設定關閉以節省 API 成本。

#### Scenario: 晨報啟用深度分析模式

- **WHEN** 晨報設定 `deep_analysis: true` 且重點股票數 ≤ 5 檔
- **THEN** 每檔股票呼叫 `Orchestrator.analyze(symbol, factor_bundle)`，將 `MultiAgentReport` 摘要附加至晨報對應段落

#### Scenario: 晨報停用深度分析模式（預設）

- **WHEN** 晨報設定 `deep_analysis: false`（預設值）
- **THEN** 晨報使用現有單一 Agent 分析邏輯，不呼叫 multi_agent_engine，維持原有執行效率
