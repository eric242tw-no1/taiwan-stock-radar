## ADDED Requirements

### Requirement: UZI 評審團 Tab 顯示三位評審評分
`/stock` 頁面的 AI 分析區域 SHALL 提供「UZI 評審」Tab，點擊後呼叫 `POST /api/analysis/uzi/{symbol}` 並顯示結果。

#### Scenario: 成功載入 UZI 評審結果
- **WHEN** 使用者點擊「UZI 評審」Tab
- **THEN** 系統顯示載入指示器並發出 API 請求

#### Scenario: 顯示三位評審分數
- **WHEN** API 回應成功（HTTP 200）
- **THEN** 系統顯示動能派、價值派、風控派三張評審卡片，各含分數（0-100）與分析理由文字

#### Scenario: 顯示加權總分
- **WHEN** 三位評審分數皆顯示
- **THEN** 系統在頂部顯示加權總分（動能 35% / 價值 35% / 風控 30%）

#### Scenario: API 請求失敗
- **WHEN** API 回應非 200 或網路錯誤
- **THEN** 系統顯示錯誤訊息「UZI 分析失敗，請重試」並提供重試按鈕

### Requirement: UZI Tab 按需載入
系統 SHALL 僅在使用者首次點擊「UZI 評審」Tab 時呼叫 API，同一個 symbol 的結果在 Tab 切換間保留（不重複呼叫）。

#### Scenario: 重複切換 Tab 不重新呼叫
- **WHEN** 使用者已載入 UZI 結果後切換至其他 Tab 再切回
- **THEN** 系統直接顯示已快取結果，不重新呼叫 API

#### Scenario: 更換 symbol 清除快取
- **WHEN** 使用者查詢新的股票代號
- **THEN** 系統清除前一個 symbol 的 UZI 結果，Tab 回到未載入狀態
