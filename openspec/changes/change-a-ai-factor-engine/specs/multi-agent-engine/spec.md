## ADDED Requirements

### Requirement: 六 Agent 多智能體協調架構

系統 SHALL 提供 `backend/agents/multi_agent_engine.py`，實作 Orchestrator 協調六個專責 Agent，透過 Claude API tool_use 驅動分析流程。

六個 Agent 職責：
- **技術分析師**：解讀技術指標，判斷趨勢與型態
- **籌碼分析師**：解讀三大法人、融資融券動向
- **總經分析師**：評估宏觀環境、產業脈絡
- **風控審查員**：評估下行風險、設定停損建議
- **交易執行員**：建議進場時機、部位大小
- **Devil's Advocate**：挑戰主流論點，提出反向質疑

#### Scenario: Orchestrator 協調分析流程

- **WHEN** 呼叫 `Orchestrator.analyze(symbol, factor_bundle)` 
- **THEN** 系統依序（或並行）呼叫六個 Agent，蒐集各自輸出，最終整合為 `MultiAgentReport`，包含各 Agent 摘要與加權綜合建議

#### Scenario: Agent 使用 tool_use 取得即時資料

- **WHEN** 技術分析師 Agent 需要追加資料（如近期新聞）
- **THEN** Agent 透過 Claude API tool_use 呼叫預定義工具（如 `get_news`、`get_price_history`），系統回傳結果後 Agent 完成分析

#### Scenario: 單一 Agent 失敗時的容錯處理

- **WHEN** 某個 Agent 呼叫逾時或 API 錯誤
- **THEN** 系統記錄錯誤、跳過該 Agent，其餘 Agent 正常輸出；`MultiAgentReport` 標記該 Agent 為 `status: "failed"`

### Requirement: Orchestrator 加權整合

系統 SHALL 依據各 Agent 的可信度權重，加權整合最終建議分數（-100 至 +100），並提供決策依據說明。

#### Scenario: 整合六 Agent 輸出為最終評分

- **WHEN** 所有 Agent 完成分析
- **THEN** Orchestrator 計算加權平均評分，評分 > 30 為買進訊號，< -30 為賣出訊號，其餘為觀望
