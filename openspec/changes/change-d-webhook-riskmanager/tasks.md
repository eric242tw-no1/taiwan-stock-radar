## 1. DB Migration

- [ ] 1.1 新增 `tv_signals` table（id, strategy_id, symbol, target_position, actual_position, diff, dedup_key, status, ai_confidence, executed_at, created_at）
- [ ] 1.2 新增 `orders` table（id, tv_signal_id, symbol, action, quantity, price, status, broker_order_id, created_at）
- [ ] 1.3 新增 `account_snapshots` table（id, date UNIQUE, total_value, cash, daily_pnl, margin_usage, created_at）
- [ ] 1.4 在 `backend/main.py` 加入 DB table 建立邏輯（或 Alembic migration）

## 2. HMAC 驗證

- [ ] 2.1 在 `backend/.env` 新增 `TV_WEBHOOK_SECRET` 變數
- [ ] 2.2 新增 `backend/utils/webhook_auth.py`：`verify_hmac(secret: str) -> bool` 使用 `hmac.compare_digest`
- [ ] 2.3 單元測試：正確 secret 通過，錯誤 secret 回傳 403

## 3. State-Based Webhook 重寫

- [ ] 3.1 將現有 `POST /api/webhook/tradingview` 複製為 `/tradingview-legacy`（過渡用，1 週後移除）
- [ ] 3.2 重寫 `POST /api/webhook/tradingview`：接收新 payload schema（含 secret + target_position）
- [ ] 3.3 實作 Redis dedup：key = `tv_signal:{strategy_id}:{symbol}:{timestamp//60}`，TTL 60s
- [ ] 3.4 被 dedup 的訊號寫入 `tv_signals` 表 `status=deduped`，回傳 200
- [ ] 3.5 實作持倉 diff 計算：呼叫 `YuantaBroker.get_position(symbol)` → 計算 diff
- [ ] 3.6 整合 Devil's Advocate：呼叫 ai_engine devil_advocate 方法，timeout 10s，低信心則 reject
- [ ] 3.7 執行 `YuantaBroker.place_order()`，寫入 `tv_signals` + `orders` 表
- [ ] 3.8 整合測試：模擬完整流程（HMAC → dedup → diff → AI → order）

## 4. 獨立 RiskManager

- [ ] 4.1 新增 `backend/services/risk_manager.py`，定義 `RiskDecision` dataclass
- [ ] 4.2 實作 `check_position_size(symbol, size, capital)`：單股 ≤ 20% 總資金
- [ ] 4.3 實作 `check_max_drawdown(account)`：當日虧損 > 5% 停止新倉
- [ ] 4.4 實作 `check_correlation_risk(symbol, portfolio)`：相關性 > 0.8 不同時持有
- [ ] 4.5 新增 `GET /api/risk/assessment/{symbol}` endpoint，回傳 `RiskDecision` JSON
- [ ] 4.6 修改 `backend/agents/stop_loss_guard.py`：停損邏輯改呼叫 `RiskManager`，移除重複邏輯
- [ ] 4.7 Webhook Devil's Advocate 前置加入 `RiskManager.check_max_drawdown()` 檢查

## 5. Yuanta 持倉真實資料

- [ ] 5.1 新增 `GET /api/portfolio/positions` endpoint：呼叫 YuantaBroker，回傳持倉列表
- [ ] 5.2 新增 `GET /api/portfolio/summary` endpoint：回傳帳戶摘要（總市值、現金、保證金）
- [ ] 5.3 修改 `frontend/app/portfolio/page.tsx`：移除 demo data，改接 `/api/portfolio/positions`
- [ ] 5.4 前端加入 30 秒 polling + WebSocket 推送持倉更新
- [ ] 5.5 套用台灣色彩慣例：紅色 = 漲/獲利、綠色 = 跌/虧損（建立 `tailwind` class 常數）
- [ ] 5.6 加入錯誤狀態：Yuanta 連線失敗顯示提示 + 最後更新時間；simulation mode 顯示 badge
- [ ] 5.7 在 `backend/main.py` APScheduler 加入 13:35 每日快照 job（寫入 `account_snapshots`）

## 6. 文件與清理

- [ ] 6.1 更新 `docs/06_tradingview_yuanta.md`：記錄新 payload 格式與 HMAC 設定方式
- [ ] 6.2 更新 TradingView Alert message 範本（放在 docs 或 README）
- [ ] 6.3 1 週後移除 `/api/webhook/tradingview-legacy` endpoint
