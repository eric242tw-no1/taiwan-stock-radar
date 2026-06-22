## Context

Taiwan Stock Radar 為 Next.js 14（App Router）前端 + FastAPI 後端的全端量化交易輔助平台。現有技術棧包含：Recharts（圖表）、Tailwind CSS（樣式）、Shadcn/UI（元件）、PostgreSQL（主資料庫）、Redis（快取/佇列）。本次 Change C 新增六項前端 UX 功能，涵蓋全新頁面、嵌入式工具元件及即時串流，屬於跨前後端的中大型變更。

## Goals / Non-Goals

**Goals:**
- 提供節點式工作流編輯器，讓使用者視覺化設計量化策略
- 建立交易日誌系統，支援情緒追蹤與事後複盤評分
- 整合現有 backtest_results 資料，產出策略績效儀表板
- 在 `/stock` 頁嵌入 ATR 停損計算器，在 `/portfolio` 嵌入部位規模計算器
- 透過 SSE 即時推送訊號至 Screener 頁面

**Non-Goals:**
- 工作流自動排程執行（由現有 Celery pipeline 負責，本次僅手動觸發）
- 行動裝置（RWD）深度優化
- 工作流版本控制 / Git 整合
- 即時 K 線圖（WebSocket tick 流）

## Decisions

### D1：工作流編輯器使用 React Flow

**選擇**：`reactflow`（@xyflow/react）  
**理由**：MIT 授權、Next.js 14 相容、內建節點/邊拖拽、可自訂節點元件。  
**替代方案**：Dagre.js（無互動 UI）、JsPlumb（商業授權）。  
**匯出格式**：JSON（`{ nodes: Node[], edges: Edge[], metadata: {} }`），儲存至 DB `workflow_definitions.definition_json`。

### D2：SSE 取代 WebSocket

**選擇**：Server-Sent Events（`/api/stream/signals`）  
**理由**：SSE 為單向推送，與 Next.js 14 Route Handler 相容，無需 WebSocket 升級層，Redis Pub/Sub 訂閱天然配合。  
**替代方案**：WebSocket（雙向但複雜度高、需 ASGI 額外設定）。  
**前端**：`useSignalStream()` hook 使用原生 `EventSource`，自動重連。

### D3：計算器為純前端 + 後端 API 混合

- **ATR 停損**：ATR 值需後端從歷史資料計算（`GET /api/risk/atr-stop/{symbol}`），前端即時顯示結果
- **部位規模計算器**：純前端計算（公式固定，不需後端），React state 即可

### D4：Analytics 頁面直接查詢現有 backtest_results

不新增新資料表，直接 JOIN `backtest_results` + `strategies` 表，以 symbol/strategy 分組聚合績效指標。夏普比率在後端計算後回傳。

### D5：DB Migration 策略

新增 `backend/services/db_migrations.py`（已存在）中加入新表建立邏輯；採用 `IF NOT EXISTS` 保護，應用啟動時自動執行。

## Risks / Trade-offs

- **[React Flow Bundle Size]** → reactflow 約 300KB gzipped，首次載入較慢 → 使用 `next/dynamic` 動態匯入，僅在 `/workflow` 頁載入
- **[Redis Pub/Sub 可靠性]** → SSE 連線中斷時訊號遺失 → 前端斷線重連時拉取最近 N 筆訊號補償
- **[ATR API 延遲]** → 歷史資料查詢可能 >500ms → 加入 Redis 快取（TTL 5 分鐘）
- **[trade_journal 無驗證]** → 情緒欄位為自由文字 → 前端下拉限制選項，後端 enum 驗證
- **[workflow run 長時間執行]** → 同步 API 會 timeout → 本次 run 以非同步 Celery task 實作，回傳 task_id

## Migration Plan

1. 執行 DB migration（自動於啟動時執行）建立 `trade_journal`、`workflow_definitions`
2. 部署後端新 router（`/api/journal`、`/api/workflow`、`/api/risk`、`/api/stream`）
3. 前端 `npm install @xyflow/react`，部署新頁面（`/workflow`、`/journal`、`/analytics`）
4. 更新 Sidebar 導覽項目
5. Rollback：移除新 router import、前端 revert Sidebar 即可；DB 表不影響現有功能

## Open Questions

- `workflow/run/{id}` 的執行結果如何回傳？建議 polling task status endpoint（沿用 `/api/tasks/{id}`）
- Analytics 夏普比率計算的無風險利率預設值？（建議 1.5% 年化，可設定）
- trade_journal 的情緒選項欄位值域？（建議：冷靜/樂觀/貪婪/恐懼/中性）
