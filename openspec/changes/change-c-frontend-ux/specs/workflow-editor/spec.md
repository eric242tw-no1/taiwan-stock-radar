## ADDED Requirements

### Requirement: 使用者可在視覺化畫布上拖拽建立工作流節點
系統 SHALL 提供 `/workflow` 頁面，使用 React Flow 畫布讓使用者從側邊面板拖拽節點至畫布。節點類型包含：資料來源（DataSource）、指標計算（Indicator）、條件判斷（Condition）、執行動作（Action）、通知（Notification）。

#### Scenario: 拖拽新增節點
- **WHEN** 使用者從左側節點面板拖拽一個節點類型至畫布
- **THEN** 系統在畫布上顯示該節點，節點帶有對應圖示與預設標籤

#### Scenario: 連接兩個節點
- **WHEN** 使用者從節點的輸出 handle 拖拽至另一節點的輸入 handle
- **THEN** 系統繪製帶箭頭的連線，代表工作流執行順序

#### Scenario: 刪除節點或連線
- **WHEN** 使用者選取節點或連線後按下 Delete 鍵
- **THEN** 系統移除該節點或連線，並自動斷開相關連線

### Requirement: 使用者可儲存與載入工作流定義
系統 SHALL 將工作流定義序列化為 JSON 並透過 `POST /api/workflow/save` 儲存至資料庫，並可透過 `GET /api/workflow/list` 列出所有工作流。

#### Scenario: 儲存工作流
- **WHEN** 使用者點擊「儲存」按鈕並輸入工作流名稱
- **THEN** 系統呼叫 `POST /api/workflow/save`，成功後顯示儲存成功提示

#### Scenario: 載入工作流
- **WHEN** 使用者從工作流清單選取一個項目
- **THEN** 系統將該 JSON 定義還原為 React Flow 節點與連線，顯示於畫布

#### Scenario: 匯出工作流 JSON
- **WHEN** 使用者點擊「匯出 JSON」
- **THEN** 系統下載包含 nodes、edges、metadata 的 JSON 檔案

#### Scenario: 匯入工作流 JSON
- **WHEN** 使用者上傳有效的工作流 JSON 檔案
- **THEN** 系統解析並渲染至畫布；若 JSON 格式無效則顯示錯誤訊息

### Requirement: 使用者可手動觸發工作流執行
系統 SHALL 提供「執行」按鈕，呼叫 `POST /api/workflow/run/{id}`，後端以 Celery 非同步執行並回傳 task_id，前端輪詢狀態。

#### Scenario: 觸發工作流執行
- **WHEN** 使用者點擊「執行」並確認
- **THEN** 系統呼叫 API 取得 task_id，並顯示執行中狀態指示器

#### Scenario: 執行完成
- **WHEN** 輪詢結果顯示 task 狀態為 SUCCESS
- **THEN** 系統顯示執行完成通知及摘要結果
