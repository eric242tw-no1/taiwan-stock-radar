## Why

Taiwan Stock Radar 目前缺乏互動式工作流編輯器、交易日誌記錄、策略績效視覺化及動態風控計算工具，使用者難以在單一平台完成「訊號分析 → 決策制定 → 交易記錄 → 績效複盤」的完整投資循環。現有 Screener 及 Backtest 頁面已累積基礎資料，亟需 UX 升級以釋放其價值。

## What Changes

- 新增 `/workflow` 頁面：可視化拖拽工作流編輯器（React Flow），支援節點式策略設計與 JSON 匯出/匯入
- 新增 `/journal` 頁面：交易日誌，記錄進出場理由、情緒、事後複盤評分，附帶統計分析
- 新增 `/analytics` 頁面：策略績效儀表板，展示累積報酬曲線、最大回撤、夏普比率（Recharts）
- 在 `/stock` 頁面嵌入 ATR 動態停損計算器 Modal（R01）
- 在持倉頁嵌入部位規模計算器工具（R02）
- 新增 WebSocket/SSE 即時訊號推送：後端 Redis Pub/Sub + 前端 `useSignalStream()` hook，Screener 顯示即時 badge

後端新增 API：
- `POST /api/workflow/save`、`GET /api/workflow/list`、`POST /api/workflow/run/{id}`
- CRUD `GET/POST/PUT/DELETE /api/journal`
- `GET /api/risk/atr-stop/{symbol}`
- SSE endpoint `GET /api/stream/signals`

DB 新增資料表：`trade_journal`、`workflow_definitions`

## Capabilities

### New Capabilities

- `workflow-editor`：可視化拖拽工作流編輯器，使用 React Flow 建立節點式策略，支援 JSON 匯出/匯入與後端執行
- `trade-journal`：交易日誌 CRUD，記錄每筆交易的進出場脈絡、情緒狀態、事後評分，附帶勝率與盈虧統計
- `strategy-analytics`：策略績效儀表板，整合 backtest_results 資料，以 Recharts 呈現累積報酬、最大回撤、夏普比率
- `atr-stop-calculator`：ATR 動態停損計算器 UI，嵌入股票分析頁，後端即時計算停損價與建議張數
- `position-sizer`：部位規模計算器，依總資金與風險比例計算建議投入金額與張數
- `realtime-signal-stream`：Redis Pub/Sub + SSE 即時訊號推送，前端 hook 訂閱並在 Screener 顯示即時 badge

### Modified Capabilities

（無現有規格層級的行為變更）

## Impact

- **前端依賴**：新增 `reactflow` 套件；`recharts` 已存在
- **後端**：新增 5 個 router 模組、2 張 DB 資料表（migration script）、Redis Pub/Sub 發布邏輯（已有 Redis）
- **DB Schema**：`trade_journal`（11 欄位）、`workflow_definitions`（id, name, definition_json, created_at, updated_at）
- **Sidebar**：新增 Workflow、Journal、Analytics 導覽項目
- **現有頁面**：`/stock` 嵌入 ATR Modal、`/portfolio` 嵌入 Position Sizer、`/screener` 新增即時 badge
