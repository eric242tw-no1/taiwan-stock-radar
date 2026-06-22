## 1. DB Schema 更新

- [x] 1.1 在 `backend/schema_sqlite.sql` 新增 `earnings_calendar` 表（`id, symbol, name, event_type, event_date, description, updated_at`）
- [x] 1.2 在 `backend/schema_sqlite.sql` 新增 `notifications` 表（`id, message, source, created_at, is_read`）
- [x] 1.3 確認 `db.py` 的 `init_db()` 執行後兩張表自動建立（`CREATE TABLE IF NOT EXISTS`）

## 2. 財報日曆後端

- [x] 2.1 建立 `backend/services/earnings_calendar.py`：`fetch_and_store_calendar(days=30)` 呼叫 FinMind，寫入 `earnings_calendar` 表，TTL 判斷避免重複拉取
- [x] 2.2 建立 `backend/routers/calendar.py`：`GET /api/calendar/events?days=30` 從 DB 讀取並回傳
- [x] 2.3 在 `backend/main.py` 註冊 `calendar` router 及 APScheduler 08:00 `fetch_and_store_calendar` 任務
- [ ] 2.4 手動測試：啟動後端，呼叫 `GET /api/calendar/events`，確認回傳格式正確

## 3. 通知中心後端

- [x] 3.1 修改 `backend/utils/telegram.py`：`send_message()` 執行後同步寫入 `notifications` 表（message, source, created_at, is_read=0）
- [x] 3.2 建立 `backend/routers/notifications.py`：`GET /api/notifications?limit=50&offset=0` 與 `PATCH /api/notifications/{id}/read`
- [x] 3.3 在 `backend/main.py` 註冊 `notifications` router 及 APScheduler 每週日 02:00 清理任務（保留最近 1000 筆）
- [ ] 3.4 手動測試：觸發任意警報，確認 DB 寫入並可透過 API 查詢

## 4. 選股進階篩選後端

- [x] 4.1 修改 `backend/routers/screener.py`：`GET /api/screener/scan` 新增 `patterns: list[str]` 與 `phase: str` 可選查詢參數
- [x] 4.2 在篩選邏輯中，呼叫 `GET /api/market/indicators/{ticker}` 取得 patterns/market_maker_intent，套用過濾條件
- [ ] 4.3 手動測試：`GET /api/screener/scan?phase=吸籌`，確認回傳僅含主力意圖=吸籌的股票

## 5. 元大證券 API 整合完善

- [x] 5.1 在 `backend/brokers/base.py` 新增 `BrokerConnectionError` 與 `BrokerOrderError` 自訂例外類別
- [x] 5.2 修改 `backend/brokers/yuanta.py`：`__init__` 若 `YUANTA_BASE_URL` 未設定則記錄 WARNING；`place_order` 在 `YUANTA_SIMULATION=true` 時回傳模擬回應而非呼叫 API
- [x] 5.3 修改 `backend/brokers/yuanta.py`：`get_positions()` 回傳加入 `qty_lots`（qty_shares / 1000）欄位
- [x] 5.4 修改 `backend/brokers/yuanta.py`：`place_order` / `cancel_order` 遭遇 4xx/5xx 時拋出 `BrokerOrderError(code, message)`
- [x] 5.5 修改 `backend/brokers/yuanta.py`：連線逾時或網路錯誤時拋出 `BrokerConnectionError`
- [ ] 5.6 手動測試（模擬模式）：設定 `YUANTA_SIMULATION=true` 後呼叫下單 API，確認回傳模擬回應且無真實委託

## 6. 財報日曆前端

- [x] 6.1 建立 `frontend/app/calendar/page.tsx`：呼叫 `GET /api/calendar/events`，以月曆格式（簡易 grid）顯示事件，色塊區分類型
- [x] 6.2 在 `frontend/components/layout/Sidebar.tsx` 加入「📅 財報日曆」連結（href: `/calendar`）
- [ ] 6.3 手動測試：確認頁面載入、事件顯示正確

## 7. 通知中心前端

- [x] 7.1 建立 `frontend/app/notifications/page.tsx`：呼叫 `GET /api/notifications`，列表顯示訊息、來源、時間、已讀狀態，點擊呼叫 PATCH 標記已讀
- [x] 7.2 修改 `frontend/components/layout/Sidebar.tsx`：「🔔 通知中心」連結旁顯示未讀數 badge（呼叫 `GET /api/notifications?limit=1` 取未讀總數）
- [ ] 7.3 手動測試：觸發警報後進入通知中心，確認訊息出現且標記已讀功能正常

## 8. 選股進階篩選前端

- [x] 8.1 修改 `frontend/app/screener/page.tsx`：在篩選區塊加入「K 線形態」多選（常見 9 種顯示為 checkbox）與「主力意圖」下拉選單（吸籌/拉抬/出貨/打壓/觀望/全部）
- [x] 8.2 將選中條件附加到 `GET /api/screener/scan` 的查詢參數
- [ ] 8.3 手動測試：選擇「吸籌」篩選，確認結果正確

## 9. 行動裝置 RWD 修正

- [x] 9.1 修改 `frontend/app/stock/page.tsx`：在 < 768px 時右側面板改為下方排列（grid 1fr），Hero Card 隱藏非必要欄位
- [x] 9.2 修改 `frontend/app/screener/page.tsx`：篩選條件區在手機改為摺疊式（預設收起），結果表格改為卡片列表
- [x] 9.3 修改 `frontend/app/portfolio/page.tsx`：持倉表格在手機改為垂直卡片，操作按鈕移至卡片內
- [ ] 9.4 手動測試：以 375px 視窗寬度瀏覽三個頁面，確認無橫向溢出

## 10. 啟動腳本更新

- [x] 10.1 更新 `start-dev.bat` 與 `啟動開發環境.bat`，確認新 router 和 scheduler 任務在正常啟動流程中生效
