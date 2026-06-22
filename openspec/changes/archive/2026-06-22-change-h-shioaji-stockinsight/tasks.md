## 1. Pine Script Alert 檔案

- [x] 1.1 建立 `tradingview/alert_strategy.pine`：包含 MA 黃金交叉 + RSI 條件，Alert JSON payload 格式與後端 TVPayload 完全相符
- [x] 1.2 建立 `tradingview/alert_webhook.pine`：Webhook URL 與 HMAC secret 佔位符說明
- [x] 1.3 在 `docs/tradingview_alert_templates.md` 補充 Pine Script 匯入步驟說明

## 2. BrokerBase 抽象層

- [x] 2.1 建立 `backend/brokers/base.py`：定義 `BrokerBase` ABC，抽象方法 `place_order`、`cancel_order`、`get_positions`、`subscribe_tick`
- [x] 2.2 建立 `backend/brokers/sinopac.py`：`SinopacBroker` 實作 BrokerBase，使用 shioaji SDK
- [x] 2.3 修改 `backend/brokers/yuanta.py`：繼承 BrokerBase，實作四個抽象方法
- [x] 2.4 在 `backend/main.py` 加入 broker 工廠：依 `BROKER` 環境變數注入 SinopacBroker 或 YuantaBroker
- [x] 2.5 在 `.env.prod.example` 加入 `SINOPAC_ACCOUNT`、`SINOPAC_PASSWORD`、`BROKER=sinopac` 說明
- [x] 2.6 在 `requirements.txt` 加入 `shioaji>=1.1.0`

## 3. Shioaji SSE 行情串流

- [x] 3.1 在 `SinopacBroker` 實作 `subscribe_tick(symbol, callback)`，透過 Shioaji API 訂閱即時 Tick
- [x] 3.2 修改 `backend/routers/stream.py`：`/api/stream/quote/{symbol}` 優先用 Shioaji Tick，fallback 至 TWSE MIS 輪詢
- [x] 3.3 修改 `frontend/hooks/useSignalStream.ts`：新增 `TickEvent` 型別與 `useTickStream` hook

## 4. StopLossGuard 雙層完整版

- [x] 4.1 重寫 `backend/agents/stop_loss_guard.py`：完整 `StopLossGuard` 類別，`__init__` 接收 broker 實例
- [x] 4.2 實作 `layer1_place_stop_order(symbol, stop_price, quantity)`：透過 broker 送出停損委託
- [x] 4.3 實作 `layer2_polling_monitor()`：每分鐘輪詢，當 current_price ≤ stop_price 執行市價賣單
- [x] 4.4 停損觸發後呼叫 `telegram.send_message` 推播通知
- [x] 4.5 在 `backend/routers/webhook.py` 的下單流程中，下單後立即初始化 StopLossGuard

## 5. ReEntry 重複信號評估

- [x] 5.1 建立 `backend/services/reentry_evaluator.py`：`evaluate(symbol, ai_confidence, positions)` → `"add" | "ignore" | "warn"`
- [x] 5.2 在 `backend/routers/webhook.py` 收到 buy 信號後，查詢持倉並呼叫 ReEntry 評估
- [x] 5.3 依決策分流：add → 半倉下單；ignore → 僅記錄；warn → Telegram 推播警告
- [x] 5.4 在 `tv_signals` 表加入 `reentry_action` 欄位（schema_sqlite.sql）

## 6. Telegram 互動按鈕

- [x] 6.1 升級 `requirements.txt`：`python-telegram-bot>=20.0`
- [x] 6.2 重寫 `backend/utils/telegram.py`：加入 `send_order_confirm(symbol, qty, price, stop_price)` 送出 inline keyboard 訊息
- [x] 6.3 建立 `backend/utils/telegram_bot.py`：Bot polling loop，`CallbackQueryHandler` 處理確認/取消/查看分析三個 callback
- [x] 6.4 在 `backend/main.py` 啟動時以 asyncio background task 運行 telegram bot polling
- [x] 6.5 實作 60 秒逾時自動取消邏輯（asyncio.wait_for 或 APScheduler 一次性任務）
- [x] 6.6 webhook 下單流程改為：送出 Telegram 確認 → 等待 callback → 確認後才 place_order

## 7. 兩段式下單確認 UI + 環境徽章

- [x] 7.1 建立 `frontend/components/OrderConfirmModal.tsx`：顯示 symbol/方向/數量/價格/停損位，確認/取消按鈕
- [x] 7.2 建立 `frontend/components/EnvBadge.tsx`：讀取 `NEXT_PUBLIC_TRADING_ENV`，模擬黃 / 正式紅
- [x] 7.3 在 `frontend/components/layout/Sidebar.tsx` 加入 EnvBadge
- [x] 7.4 在 `.env.prod.example` 加入 `TRADING_ENV=simulation` 與 `NEXT_PUBLIC_TRADING_ENV=simulation`

## 8. 三級快取

- [x] 8.1 建立 `backend/services/cache.py`：`CacheService` 類別，`get(key)` / `set(key, value, ttl)` 介面
- [x] 8.2 實作 L1（記憶體 dict，TTL 5s）層
- [x] 8.3 實作 L2（Redis，TTL 60s）層，使用現有 `REDIS_URL`
- [x] 8.4 實作 L3（SQLite `cache` 表，TTL 300s）層
- [x] 8.5 修改 `backend/routers/stock.py`：`/api/stock/{symbol}/quote` 套用 CacheService
- [x] 8.6 修改 `backend/routers/market.py`：`/api/market/indicators/{symbol}` 套用 CacheService
- [x] 8.7 修改 `backend/routers/stock.py`：`/api/stock/{symbol}/chip` 套用 CacheService
- [x] 8.8 在 `schema_sqlite.sql` 加入 `cache` 表（key, value, expires_at）

## 9. K 線形態識別 27 種

- [x] 9.1 建立 `backend/services/candlestick.py`：純 Python + numpy 實作 27 種形態識別函式
- [x] 9.2 實作單根 9 種：錘子/倒錘子/流星/上吊/十字星/長十字/墓碑十字/蜻蜓十字/紡錘
- [x] 9.3 實作雙根 9 種：多頭吞噬/空頭吞噬/穿頭破腳/烏雲罩頂/母子線×2/平頂/平底/切入
- [x] 9.4 實作三根 9 種：晨星/夜星/三白兵/三黑鴉/紅三兵/黑三兵/上升三法/下降三法/棄嬰
- [x] 9.5 修改 `backend/routers/market.py`：indicators 回應加入 `patterns` 欄位
- [x] ⚠️ 需補前端 UI：在 `frontend/app/stock/page.tsx` 技術指標區塊顯示 `patterns`（偵測到的 K 線形態 badge 列表）

## 10. AI Self Audit 自審計

- [x] 10.1 在 `schema_sqlite.sql` 加入 `ai_audit` 表（symbol, predicted_direction, target_price, confidence, predicted_at, actual_close, is_correct）
- [x] 10.2 建立 `backend/services/audit.py`：`record_prediction()` 與 `run_daily_audit()` 函式
- [x] 10.3 修改 `backend/routers/analysis.py`：UZI/IC/辯論 API 呼叫後寫入 `ai_audit`
- [x] 10.4 建立 `backend/routers/audit.py`：`GET /api/audit/accuracy?days=N` 返回準確率報表
- [x] 10.5 在 `backend/main.py` APScheduler 加入每日 15:30 `run_daily_audit` 任務
- [x] ⚠️ 需補前端 UI：新增 `frontend/app/audit/page.tsx` 頁面，呼叫 `GET /api/audit/accuracy` 顯示準確率報表（折線圖 + 表格），並在 Sidebar 加入「🎯 AI 自審計」連結

## 11. 主力意圖四階段分析

- [x] 11.1 建立 `backend/services/market_maker.py`：`detect_phase(chip, indicators)` → `{phase, confidence, signals}`
- [x] 11.2 實作四階段規則：吸籌 / 拉抬 / 出貨 / 打壓（依 design.md 規則）
- [x] 11.3 修改 `backend/routers/market.py`：indicators 回應加入 `market_maker_intent` 欄位
- [x] ⚠️ 需補前端 UI（原 spec 11.4）：在 `frontend/app/stock/page.tsx` 籌碼分析區塊加入「主力意圖」顯示卡片，欄位：phase / confidence / signals 列表
