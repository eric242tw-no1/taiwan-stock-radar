## 1. 基礎建設與 DB Migration

- [x] 1.1 在 `backend/services/db_migrations.py` 新增 `trade_journal` 資料表建立 SQL（IF NOT EXISTS）
- [x] 1.2 在 `backend/services/db_migrations.py` 新增 `workflow_definitions` 資料表建立 SQL（IF NOT EXISTS）
- [x] 1.3 更新 `backend/schema.sql` 加入兩張新資料表的 DDL
- [x] 1.4 確認應用啟動時 migration 自動執行並通過 smoke test

## 2. 後端 API — 工作流編輯器

- [x] 2.1 建立 `backend/routers/workflow.py`，實作 `GET /api/workflow/list` 回傳工作流清單
- [x] 2.2 實作 `POST /api/workflow/save`，儲存 `{ name, definition_json }` 至 `workflow_definitions`
- [x] 2.3 實作 `POST /api/workflow/run/{id}`，以 Celery task 非同步執行並回傳 `task_id`
- [x] 2.4 在 `backend/main.py` 註冊 workflow router

## 3. 後端 API — 交易日誌

- [x] 3.1 建立 `backend/routers/journal.py`，實作 `GET /api/journal`（分頁、排序）
- [x] 3.2 實作 `POST /api/journal`，含欄位驗證（Pydantic model）
- [x] 3.3 實作 `PUT /api/journal/{id}` 與 `DELETE /api/journal/{id}`
- [x] 3.4 在 `backend/main.py` 註冊 journal router

## 4. 後端 API — 風險計算器

- [x] 4.1 建立 `backend/routers/risk.py`，實作 `GET /api/risk/atr-stop/{symbol}`
- [x] 4.2 從歷史資料計算 14 日 ATR，加入 Redis 快取（TTL 300 秒）
- [x] 4.3 支援可選參數 `entry_price`、`multiplier`、`capital`、`risk_pct`，計算停損價與建議張數
- [x] 4.4 在 `backend/main.py` 註冊 risk router

## 5. 後端 API — Analytics

- [x] 5.1 建立 `backend/routers/analytics.py`，實作 `GET /api/analytics/strategies`
- [x] 5.2 查詢 `backtest_results`，計算夏普比率（無風險利率 1.5% 年化）與最大回撤
- [x] 5.3 回傳每日累積報酬序列供前端繪圖
- [x] 5.4 在 `backend/main.py` 註冊 analytics router

## 6. 後端 API — SSE 即時訊號流

- [x] 6.1 建立 `backend/routers/stream.py`，實作 SSE endpoint `GET /api/stream/signals`
- [x] 6.2 訂閱 Redis channel `signals:realtime`，將事件轉發至 SSE 客戶端
- [x] 6.3 加入心跳機制（每 30 秒發送 `:ping\n\n`）
- [x] 6.4 在 Webhook 觸發完成後 publish 事件至 `signals:realtime`（修改現有 webhook router）
- [x] 6.5 在 `backend/main.py` 註冊 stream router

## 7. 前端 — 安裝依賴與基礎設定

- [x] 7.1 執行 `npm install @xyflow/react` 並更新 `frontend/package.json`
- [x] 7.2 在 `frontend/components/layout/Sidebar.tsx` 新增 Workflow、Journal、Analytics 導覽項目

## 8. 前端 — 工作流編輯器頁面

- [x] 8.1 建立 `frontend/app/workflow/page.tsx`，使用 `next/dynamic` 動態匯入 React Flow
- [x] 8.2 建立節點面板元件，包含 5 種節點類型拖拽區塊
- [x] 8.3 實作自訂節點元件（DataSource、Indicator、Condition、Action、Notification）
- [x] 8.4 實作儲存功能（呼叫 `POST /api/workflow/save`）與工作流名稱 Dialog
- [x] 8.5 實作工作流清單 Dropdown（`GET /api/workflow/list`）與載入功能
- [x] 8.6 實作 JSON 匯出（瀏覽器下載）與匯入（file input 解析）
- [x] 8.7 實作「執行」按鈕，呼叫 run API 並輪詢 `/api/tasks/{task_id}` 顯示狀態

## 9. 前端 — 交易日誌頁面

- [x] 9.1 建立 `frontend/app/journal/page.tsx`，含統計卡片區（勝率、平均盈虧、情緒分布）
- [x] 9.2 建立交易清單元件，支援分頁（20 筆/頁）與依日期排序
- [x] 9.3 建立「新增交易」Dialog/Form，含所有欄位與前端驗證
- [x] 9.4 實作「編輯」行內 Dialog（預填現有資料，呼叫 PUT API）
- [x] 9.5 實作「刪除」確認 Dialog（呼叫 DELETE API）
- [x] 9.6 以 Recharts BarChart 實作情緒分布橫條圖

## 10. 前端 — 策略績效儀表板

- [x] 10.1 建立 `frontend/app/analytics/page.tsx`，顯示策略績效卡片清單
- [x] 10.2 實作策略卡片元件，含總報酬率、最大回撤、夏普比率、交易次數
- [x] 10.3 點擊卡片展開 Recharts LineChart，繪製累積報酬曲線
- [x] 10.4 實作多策略 checkbox 選取與疊加比較圖

## 11. 前端 — ATR 停損計算器

- [x] 11.1 建立 `frontend/components/AtrStopModal.tsx` Modal 元件
- [x] 11.2 實作表單（股票代號預填、買入價、ATR 倍數輸入）與送出邏輯
- [x] 11.3 顯示計算結果：ATR 值、停損價、停損金額、停損比例、建議張數
- [x] 11.4 在 `frontend/app/stock/page.tsx` 加入「ATR 停損計算器」按鈕，開啟 Modal

## 12. 前端 — 部位規模計算器

- [x] 12.1 建立 `frontend/components/PositionSizer.tsx` 元件（純前端計算）
- [x] 12.2 實作即時計算邏輯（onChange 觸發，debounce 100ms）
- [x] 12.3 實作風險等級警示（投入比例 > 50% 顯示橘色警示）
- [x] 12.4 嵌入 `frontend/app/portfolio/page.tsx`

## 13. 前端 — 即時訊號推送

- [x] 13.1 建立 `frontend/hooks/useSignalStream.ts`，使用 `EventSource` 訂閱 SSE
- [x] 13.2 實作斷線自動重連（3 秒後重試）與最近 10 筆訊號補償請求
- [x] 13.3 回傳型別安全介面 `{ signals: Signal[], isConnected: boolean, error: string | null }`
- [x] 13.4 在 `frontend/app/screener/page.tsx` 引入 hook，在訊號欄顯示即時 badge
- [x] 13.5 實作 badge 計數（多訊號累積）與點擊展開訊號清單
- [x] 13.6 badge 60 秒無互動後自動消失

## 14. 測試與整合驗證

- [ ] 14.1 手動測試工作流編輯器：拖拽節點、連線、儲存、載入、JSON 匯出
- [ ] 14.2 手動測試交易日誌：新增、編輯、刪除、統計卡片正確性
- [ ] 14.3 手動測試 Analytics：策略卡片顯示、報酬曲線、多策略比較
- [ ] 14.4 手動測試 ATR 計算器：有效輸入、歷史資料不足錯誤處理
- [ ] 14.5 手動測試 SSE：開啟 Screener，觸發 Webhook，確認 badge 出現
- [ ] 14.6 確認 Sidebar 新增項目導覽正確
- [x] 14.7 更新 `啟動開發環境.bat` 確認無新依賴遺漏
