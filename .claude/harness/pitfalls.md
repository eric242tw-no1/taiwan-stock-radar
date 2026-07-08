# 踩坑紀錄（append-only）

寫入格式見 [F-knowledge-protocol.md](F-knowledge-protocol.md) 第 2 節。每坑一段，新的加在最上面。
超過 10 條或 120 行 → 觸發整併程序（F 第 3 節）。

---

## [2026-07-04] TradingView 嵌入 widget 不支援台股，永遠顯示 S&P 500
- 症狀：iframe 嵌入 TradingView（widgetembed 或 embed-widget）傳 `TWSE:2330`，畫面永遠是 S&P 500；改用官方新格式（hash JSON）後 symbol 有載入但跳「此商品僅在TradingView上可用」、OHLC 全為 Ø
- 根因：TWSE 資料**不授權給任何嵌入式 widget**（licensing 限制），不是 URL 格式問題；舊 widgetembed 的 query symbol 被忽略只是把問題掩蓋成默默 fallback SPX
- 正確做法：台股一律用 `openTvInBrowser()`（components/TradingViewModal.tsx）開系統瀏覽器的 `https://www.tradingview.com/chart/?symbol=TWSE%3A2330`（完整版正常）；美股嵌入可用，嵌入格式＝官方 `embed-widget/advanced-chart/?locale=xx#<encodeURIComponent(JSON config)>`
- 驗證方式：Chrome 直開 widget URL 截圖看實際渲染（preview_screenshot 對 TV 的 WebGL 圖表會逾時，別用）
- 來源：實測（Chrome 截圖確認 widget 彈窗與完整版正常）

## [2026-07-04] webhook 整合測試 stub 從未生效（patch 錯目標）
- 症狀：test_webhook_flow 每測卡 60 秒後回 `{"status":"timeout"}`；或 `AttributeError: module 'routers.webhook' has no attribute 'devil_advocate'`
- 根因：handler 在函式內才 `from main import _broker`、`from agents.ai_engine import devil_advocate`，patch routers.webhook 層級的名稱無效；且下單流程有 Telegram 60 秒確認等待，測試原本沒 stub
- 正確做法：patch `main._broker`、`agents.ai_engine.devil_advocate`、`utils.telegram_bot.register_pending`（回傳已 set 的 asyncio.Event）、`utils.telegram_bot.is_confirmed`、`utils.telegram.send_order_confirm`
- 驗證方式：backend 下 `.venv\Scripts\python.exe -m pytest tests\test_webhook_flow.py` → 5 passed 且 < 10 秒
- 來源：實測
