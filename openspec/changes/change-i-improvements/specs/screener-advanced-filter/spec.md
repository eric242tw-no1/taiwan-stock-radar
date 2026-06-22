## ADDED Requirements

### Requirement: 選股工作流支援 K 線形態篩選條件
系統 SHALL 在 `GET /api/screener/scan` 支援 `patterns` 查詢參數，過濾出包含指定形態的股票。

#### Scenario: 以形態篩選
- **WHEN** `GET /api/screener/scan?patterns=多頭吞噬,晨星`
- **THEN** 回傳最近 K 線含有「多頭吞噬」或「晨星」任一形態的股票列表

#### Scenario: 無形態條件時不過濾
- **WHEN** `GET /api/screener/scan` 未帶 `patterns` 參數
- **THEN** 行為與現有相同，不做形態過濾

### Requirement: 選股工作流支援主力意圖篩選條件
系統 SHALL 在 `GET /api/screener/scan` 支援 `phase` 查詢參數，過濾出主力意圖符合指定階段的股票。

#### Scenario: 以主力階段篩選
- **WHEN** `GET /api/screener/scan?phase=吸籌`
- **THEN** 回傳 `market_maker_intent.phase == "吸籌"` 的股票

#### Scenario: 多條件組合
- **WHEN** `GET /api/screener/scan?patterns=晨星&phase=吸籌&min_score=60`
- **THEN** 回傳同時滿足所有條件的股票

### Requirement: 選股前端新增進階篩選 UI
系統 SHALL 在 `/screener` 頁面篩選區塊新增「K 線形態」多選 checkbox 與「主力意圖」下拉選單。

#### Scenario: 形態多選
- **WHEN** 使用者勾選「多頭吞噬」、「晨星」
- **THEN** 觸發篩選，結果僅顯示含有任一形態的股票

#### Scenario: 主力意圖下拉
- **WHEN** 使用者選擇「吸籌」
- **THEN** 觸發篩選，結果僅顯示 phase=吸籌 的股票
