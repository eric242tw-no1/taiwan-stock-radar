## ADDED Requirements

### Requirement: 重複信號 ReEntry 評估
系統 SHALL 在收到相同股票的重複 buy 信號時，依持倉狀態與信心分數決策：加碼 / 忽略 / 警示，而非直接去重拋棄。

#### Scenario: 無持倉時重複信號視為首次入場
- **WHEN** 收到 symbol X 的 buy 信號，且 X 目前持倉為 0
- **THEN** 正常執行下單流程，不觸發 ReEntry 評估

#### Scenario: 有持倉且新信號信心 > 75 → 加碼
- **WHEN** 收到 symbol X 的 buy 信號，X 已有持倉，新信號 `ai_confidence > 0.75`
- **THEN** 系統決策為「加碼」，下單數量為原倉位的 50%，並記錄 reentry_action = "add"

#### Scenario: 有持倉且新信號信心 40-75 → 忽略
- **WHEN** 收到 symbol X 的 buy 信號，X 已有持倉，`0.40 <= ai_confidence <= 0.75`
- **THEN** 系統決策為「忽略」，不下單，記錄 reentry_action = "ignore"

#### Scenario: 有持倉且新信號信心 < 40 → 警示
- **WHEN** 收到 symbol X 的 buy 信號，X 已有持倉，`ai_confidence < 0.40`
- **THEN** 系統決策為「警示」，不下單，透過 Telegram 推播警告訊息，記錄 reentry_action = "warn"
