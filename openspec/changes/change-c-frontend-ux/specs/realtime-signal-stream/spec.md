## ADDED Requirements

### Requirement: 後端透過 Redis Pub/Sub 發布即時訊號事件
系統 SHALL 在以下情境發布訊號至 Redis channel `signals:realtime`：Webhook 觸發新訊號時、AI 評分完成時。後端提供 SSE endpoint `GET /api/stream/signals`，訂閱該 channel 並將事件推送至連線的前端客戶端。

#### Scenario: Webhook 觸發訊號推送
- **WHEN** TradingView Webhook 呼叫後端並觸發新訊號
- **THEN** 後端在處理完成後於 500ms 內 publish 事件至 Redis，SSE 客戶端收到該事件

#### Scenario: SSE 連線建立
- **WHEN** 前端呼叫 `GET /api/stream/signals`
- **THEN** 後端回傳 `Content-Type: text/event-stream`，保持長連線並推送心跳（每 30 秒）

#### Scenario: SSE 斷線重連
- **WHEN** 網路中斷導致 SSE 連線關閉
- **THEN** 前端 `useSignalStream()` hook 於 3 秒後自動重連，並請求最近 10 筆訊號補償

### Requirement: Screener 頁面顯示即時訊號 Badge
系統 SHALL 在 Screener 頁面的訊號欄位旁，當收到即時訊號時顯示動態 badge（紅點 + 「新訊號」文字），並列出最新訊號摘要（股票代號、訊號類型、時間戳）。

#### Scenario: 收到新訊號顯示 Badge
- **WHEN** `useSignalStream()` hook 收到新的訊號事件
- **THEN** Screener 頁面於 1 秒內在對應股票列顯示紅點 badge，同時觸發瀏覽器通知（若已授權）

#### Scenario: Badge 自動消失
- **WHEN** 使用者點擊 badge 或超過 60 秒未互動
- **THEN** badge 消失，訊號記錄移至「今日訊號」清單

#### Scenario: 多訊號累積
- **WHEN** 在使用者查看前收到 3 個以上新訊號
- **THEN** badge 顯示數字計數（如「3」），點擊後展開訊號清單

### Requirement: useSignalStream Hook 提供型別安全介面
系統 SHALL 提供 `useSignalStream()` React hook，回傳 `{ signals: Signal[], isConnected: boolean, error: string | null }`，Signal 型別包含 `symbol`、`type`、`score`、`timestamp` 欄位。

#### Scenario: Hook 初始狀態
- **WHEN** 元件掛載並呼叫 `useSignalStream()`
- **THEN** `isConnected` 初始為 false，建立 SSE 連線後變為 true

#### Scenario: 連線失敗錯誤處理
- **WHEN** SSE endpoint 回傳非 200 狀態碼
- **THEN** `error` 欄位設為錯誤訊息，`isConnected` 為 false，hook 停止重試
