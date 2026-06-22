## 1. /stock 頁面 AI Tab 框架

- [x] 1.1 在 `/stock` 頁面 AI Score 卡片下方新增 Tab 列（UZI 評審 / IC 備忘錄 / 多空辯論）
- [x] 1.2 實作 Tab 狀態管理（activeAiTab state）與切換邏輯
- [x] 1.3 實作 per-symbol 快取結構（換 symbol 時清除三個 Tab 的資料與 loading 狀態）

## 2. UZI 評審 Tab

- [x] 2.1 實作 fetchUzi(symbol) — 呼叫 `POST /api/analysis/uzi/{symbol}`，包含 loading / error state
- [x] 2.2 實作 UZI 評審卡片元件：三位評審（動能/價值/風控）各一張，顯示分數與理由
- [x] 2.3 顯示加權總分（動能 35% / 價值 35% / 風控 30%）
- [x] 2.4 實作 Tab 按需載入：點擊才 fetch，結果保留至換 symbol

## 3. IC 備忘錄 Tab

- [x] 3.1 實作 fetchIcMemo(symbol) — 呼叫 `GET /api/analysis/ic-memo/{symbol}`，包含 loading / error state
- [x] 3.2 實作 IC 備忘錄情境卡元件：Bull（綠）/ Base（灰）/ Bear（紅）三張，顯示條件、目標價、停損、EV
- [x] 3.3 在情境卡右上角顯示 generated_at 時間戳
- [x] 3.4 實作 Tab 按需載入與跨 Tab 快取

## 4. 多空辯論 Tab

- [x] 4.1 實作 fetchDebate(symbol) — 呼叫 `POST /api/analysis/debate/{symbol}`，60s timeout，包含 loading / error state
- [x] 4.2 實作辯論面板元件：BullAgent（綠）→ BearAgent（紅）→ ArbiterAgent（藍）依序顯示論點與信心分數
- [x] 4.3 超過 30 秒顯示「AI 深度分析中，請稍候...」提示
- [x] 4.4 請求超時（60s）或失敗時顯示錯誤訊息與重試按鈕
- [x] 4.5 換 symbol 時取消進行中的 AbortController 請求

## 5. /strategy 策略版本頁面

- [x] 5.1 建立 `frontend/app/strategy/page.tsx` 新頁面
- [x] 5.2 實作 fetchVersions() — 呼叫 `GET /api/strategies/versions` 顯示版本列表
- [x] 5.3 實作版本卡片列表：顯示版本名稱、建立時間、active 標記
- [x] 5.4 實作新增版本表單（版本名稱 + prompt template textarea + 送出按鈕）
- [x] 5.5 實作 createVersion() — 呼叫 `POST /api/strategies/versions`，成功後重新載入列表
- [x] 5.6 版本名稱空值驗證：未填時顯示欄位錯誤，不送出請求

## 6. Sidebar 更新

- [x] 6.1 在 `frontend/components/layout/Sidebar.tsx` 新增「📋 策略版本」連結，指向 `/strategy`

## 7. 手動驗證

- [x] 7.1 `/stock?symbol=2330` → 點擊三個 AI Tab，確認各自載入並顯示正確資料
- [x] 7.2 確認切換 Tab 後再切回不重複呼叫 API（Network 面板確認）
- [x] 7.3 確認換 symbol 後三個 Tab 資料清除
- [x] 7.4 `/strategy` 頁面：新增版本、列表顯示、空欄位驗證
- [x] 7.5 Sidebar「策略版本」連結正確導向
