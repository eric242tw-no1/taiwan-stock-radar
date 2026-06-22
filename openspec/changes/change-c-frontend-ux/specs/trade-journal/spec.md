## ADDED Requirements

### Requirement: 使用者可新增交易日誌記錄
系統 SHALL 提供 `/journal` 頁面，包含「新增交易」表單，欄位涵蓋：股票代號、進場日期、出場日期、進場價、出場價、盈虧（自動計算）、進出場理由、情緒狀態（冷靜/樂觀/貪婪/恐懼/中性）、複盤評分（1-10）、備註。資料透過 `POST /api/journal` 寫入 `trade_journal` 資料表。

#### Scenario: 新增有效交易記錄
- **WHEN** 使用者填寫必填欄位（股票代號、進場日期、進場價、情緒）並送出
- **THEN** 系統呼叫 `POST /api/journal`，成功後記錄出現在清單頂端，盈虧自動計算

#### Scenario: 缺少必填欄位
- **WHEN** 使用者未填股票代號就送出表單
- **THEN** 系統顯示欄位驗證錯誤，不送出 API 請求

### Requirement: 使用者可檢視、編輯、刪除交易日誌
系統 SHALL 提供可排序分頁的清單（`GET /api/journal`），並支援點擊展開編輯（`PUT /api/journal/{id}`）及刪除（`DELETE /api/journal/{id}`）。

#### Scenario: 瀏覽交易清單
- **WHEN** 使用者進入 `/journal` 頁面
- **THEN** 系統顯示所有交易記錄，預設依進場日期降冪排列，每頁 20 筆

#### Scenario: 編輯交易記錄
- **WHEN** 使用者點擊某筆記錄的「編輯」按鈕並修改複盤評分
- **THEN** 系統呼叫 `PUT /api/journal/{id}`，成功後清單即時更新

#### Scenario: 刪除交易記錄
- **WHEN** 使用者點擊「刪除」並確認對話框
- **THEN** 系統呼叫 `DELETE /api/journal/{id}`，記錄從清單移除

### Requirement: 系統顯示交易統計摘要
系統 SHALL 在清單上方顯示統計卡片：總交易數、勝率（%）、平均盈虧（元）、情緒分布（各情緒佔比橫條圖）。

#### Scenario: 計算勝率
- **WHEN** 使用者進入 `/journal` 頁面且有至少一筆已出場記錄
- **THEN** 勝率卡片顯示（盈利筆數 / 已出場總筆數）× 100%

#### Scenario: 情緒分布圖
- **WHEN** 有多筆不同情緒狀態的交易記錄
- **THEN** 系統以橫條圖顯示各情緒標籤的佔比
