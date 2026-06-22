## ADDED Requirements

### API Endpoints
- `GET /api/portfolio/positions` → 回傳當前持倉列表（symbol、張數、成本、現價、P&L、P&L%）
- `GET /api/portfolio/summary` → 回傳帳戶摘要（總市值、現金、保證金使用率、當日損益）

### 前端持倉頁面
- `frontend/app/portfolio/page.tsx` 移除 demo data，改接 `/api/portfolio/positions`
- WebSocket 30 秒更新（`setInterval` → `GET /api/portfolio/positions` → 推送更新）
- 顯示欄位：股票代號、持股張數、成本均價、現價、損益金額、損益%
- **台灣色彩慣例**：紅色 = 漲/獲利、綠色 = 跌/虧損

### 錯誤狀態
- Yuanta API 連線失敗 → 顯示 "無法連線至元大，請確認帳戶設定" + 最後更新時間
- `YUANTA_LIVE=false`（預設）→ 顯示 simulation 標記 badge

### account_snapshots 每日快照
- APScheduler 每日 13:35 收盤後寫入 `account_snapshots`（date、總市值、現金、當日損益）
