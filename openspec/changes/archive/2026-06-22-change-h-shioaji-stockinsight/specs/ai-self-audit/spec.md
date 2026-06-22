## ADDED Requirements

### Requirement: AI 預測自審計
系統 SHALL 記錄每筆 AI 分析的預測方向、目標價、信心分數，並在次日 15:30 自動比對實際收盤價，計算預測準確率。

#### Scenario: AI 分析結果寫入 ai_audit 表
- **WHEN** 呼叫任何 AI 分析 API（UZI/IC/辯論）
- **THEN** 寫入 `ai_audit` 表：symbol、predicted_direction、target_price、confidence、predicted_at

#### Scenario: 每日 15:30 自動比對
- **WHEN** APScheduler 觸發每日 15:30 審計任務
- **THEN** 查詢當日所有 `actual_close IS NULL` 的記錄，填入當日收盤價，計算 `is_correct`

#### Scenario: GET /api/audit/accuracy 返回準確率報表
- **WHEN** 呼叫 `GET /api/audit/accuracy?days=30`
- **THEN** 返回 30 日內各方向（買/賣/觀望）的預測準確率與樣本數
