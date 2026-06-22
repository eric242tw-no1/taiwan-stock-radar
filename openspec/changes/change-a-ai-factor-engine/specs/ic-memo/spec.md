## ADDED Requirements

### Requirement: Investment Committee 備忘錄

系統 SHALL 提供 `GET /api/analysis/ic-memo/{symbol}` API，回傳 IC 備忘錄，包含 bull/base/bear 三情境分析與加權期望值計算。IC 備忘錄結果須持久化至 `ic_memo` DB 表。

#### Scenario: 取得最新 IC 備忘錄

- **WHEN** 客戶端請求 `GET /api/analysis/ic-memo/{symbol}`
- **THEN** 系統回傳該股票最近一次的 IC 備忘錄 JSON，包含三個情境（bull/base/bear）的目標價、機率、關鍵假設，以及加權期望值

#### Scenario: 首次請求觸發 IC 備忘錄生成

- **WHEN** `ic_memo` 表中無該股票當日記錄
- **THEN** 系統透過 Claude API 生成三情境分析，計算期望值（bull_price × bull_prob + base_price × base_prob + bear_price × bear_prob），寫入 DB 後回傳

#### Scenario: 期望值計算邏輯

- **WHEN** 三情境機率總和不等於 100%
- **THEN** 系統自動正規化（各情境機率 / 總機率），確保期望值計算正確

#### Scenario: IC 備忘錄 JSON 格式

- **WHEN** 系統回傳 IC 備忘錄
- **THEN** 回應 JSON 包含：`symbol`、`date`、`scenarios`（bull/base/bear，每個含 `target_price`、`probability`、`key_assumptions` 陣列）、`expected_value`、`current_price`、`upside_pct`
