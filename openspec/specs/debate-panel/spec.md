# Spec: debate-panel

## Purpose

多空辯論面板 — 在 `/stock` 頁面提供 AI 多空辯論 Tab，協調 BullAgent / BearAgent / ArbiterAgent 執行辯論並呈現結果。

## Requirements

### Requirement: 多空辯論 Tab 顯示辯論流程
`/stock` 頁面 SHALL 提供「多空辯論」Tab，點擊後呼叫 `POST /api/analysis/debate/{symbol}` 並顯示 BullAgent / BearAgent / ArbiterAgent 辯論結果。

#### Scenario: 點擊 Tab 觸發辯論 API
- **WHEN** 使用者點擊「多空辯論」Tab
- **THEN** 系統顯示骨架載入畫面並發出辯論 API 請求

#### Scenario: 顯示辯論超時提示
- **WHEN** 請求超過 30 秒仍未回應
- **THEN** 系統在骨架畫面上方顯示「AI 深度分析中，請稍候（可能需要 30-60 秒）」

#### Scenario: 顯示辯論結果
- **WHEN** API 回應成功（HTTP 200）
- **THEN** 系統依序顯示：BullAgent 論點（綠色）、BearAgent 論點（紅色）、ArbiterAgent 結論（藍色），含各自的信心分數

#### Scenario: 顯示最終裁決
- **WHEN** ArbiterAgent 結論顯示
- **THEN** 系統在底部顯示高亮裁決方向（看多/看空/中性）與建議行動

#### Scenario: API 超時或失敗
- **WHEN** API 在 60 秒內未回應或回傳錯誤
- **THEN** 系統顯示「辯論分析超時，請重試」並提供重試按鈕

### Requirement: 多空辯論慢速 API 的 UX 處理
系統 SHALL 在辯論 API 呼叫期間維持頁面其他功能可互動（不 block UI）。

#### Scenario: 辯論進行中切換至其他 Tab
- **WHEN** 辯論 API 仍在執行時使用者切換至其他 Tab
- **THEN** 請求繼續在背景執行，切回時若已完成則顯示結果

#### Scenario: 更換 symbol 中止舊請求
- **WHEN** 使用者查詢新 symbol 時辯論請求仍進行中
- **THEN** 系統取消舊請求並清除結果
