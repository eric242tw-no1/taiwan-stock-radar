## ADDED Requirements

### Requirement: 系統顯示各策略歷史回測績效總覽
系統 SHALL 在 `/analytics` 頁面提供策略績效總覽卡片，資料來源為 `backtest_results` 資料表，每張卡片顯示：策略名稱、股票代號、總報酬率（%）、最大回撤（%）、夏普比率、交易次數。

#### Scenario: 進入 Analytics 頁面
- **WHEN** 使用者導航至 `/analytics`
- **THEN** 系統顯示所有策略的績效卡片清單，依總報酬率降冪排列

#### Scenario: 無回測資料
- **WHEN** backtest_results 表為空
- **THEN** 系統顯示引導訊息「尚無回測結果，請至回測頁面執行策略」

### Requirement: 系統以累積報酬曲線圖呈現策略績效
系統 SHALL 在策略卡片點擊後展開 Recharts LineChart，X 軸為日期，Y 軸為累積報酬率（%），可選擇多策略疊加比較。

#### Scenario: 查看單一策略報酬曲線
- **WHEN** 使用者點擊某策略卡片
- **THEN** 系統展開 LineChart，顯示該策略從起始日至結束日的每日累積報酬曲線

#### Scenario: 多策略比較
- **WHEN** 使用者勾選多個策略的 checkbox
- **THEN** 系統在同一 LineChart 以不同顏色繪製各策略曲線，並顯示圖例

### Requirement: 系統計算並展示夏普比率與最大回撤
後端 SHALL 於 `GET /api/analytics/strategies` 回傳夏普比率（假設無風險利率 1.5% 年化）及最大回撤值，前端以數字卡片顯示。

#### Scenario: 夏普比率計算
- **WHEN** 策略有至少 20 個交易日的報酬資料
- **THEN** 後端回傳以年化標準差計算的夏普比率，前端顯示至小數點後兩位

#### Scenario: 最大回撤顯示
- **WHEN** 策略有完整報酬序列
- **THEN** 系統以紅色數字顯示最大回撤百分比，並標示發生日期區間
