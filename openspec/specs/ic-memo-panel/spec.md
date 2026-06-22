# Spec: ic-memo-panel

## Purpose

IC 備忘錄面板 — 在 `/stock` 頁面提供「IC 備忘錄」Tab，呈現 Bull / Base / Bear 三情境分析卡，支援按需載入與 symbol 切換清除。

## Requirements

### Requirement: IC 備忘錄 Tab 顯示三情境卡
`/stock` 頁面 SHALL 提供「IC 備忘錄」Tab，點擊後呼叫 `GET /api/analysis/ic-memo/{symbol}` 並顯示 Bull/Base/Bear 三情境分析。

#### Scenario: 成功載入 IC 備忘錄
- **WHEN** 使用者點擊「IC 備忘錄」Tab
- **THEN** 系統呼叫 API 並顯示三張情境卡（Bull 綠色、Base 灰色、Bear 紅色）

#### Scenario: 顯示情境內容
- **WHEN** API 回應成功
- **THEN** 每張情境卡顯示：情境名稱、發生條件、目標價、停損價、期望值（EV）

#### Scenario: 顯示快取時間戳
- **WHEN** IC 備忘錄來自 DB 快取（非即時生成）
- **THEN** 系統在右上角顯示「生成時間：{generated_at}」

#### Scenario: API 失敗
- **WHEN** API 回應非 200
- **THEN** 系統顯示「IC 備忘錄生成失敗，請重試」

### Requirement: IC 備忘錄按需載入與快取
系統 SHALL 僅在首次點擊時呼叫 API，同一 symbol 結果在 Tab 切換間保留。

#### Scenario: Tab 切換不重複呼叫
- **WHEN** IC 備忘錄已載入後使用者切換 Tab 再切回
- **THEN** 系統直接顯示已載入結果

#### Scenario: 更換 symbol 清除快取
- **WHEN** 使用者查詢新的股票代號
- **THEN** 系統清除前一個 symbol 的 IC 備忘錄結果
