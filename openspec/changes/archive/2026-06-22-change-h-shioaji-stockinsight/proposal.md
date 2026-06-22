## Why

專案目前有 4 項功能未實作（Pine Script、ReEntry、Telegram 互動按鈕、Sprint 規劃），且券商層綁定元大、無抽象介面，無法快速切換至永豐金 Shioaji Pro。同時缺少三級快取、K 線形態識別、AI 自審計、主力意圖分析等核心量化功能，整體競爭力不足。

## What Changes

- 補齊 TradingView Pine Script Alert `.pine` 檔（可直接匯入 TV）
- 新增 ReEntry 重複信號評估（加碼 / 忽略 / 警示三種決策邏輯）
- Telegram Bot 升級為雙向互動（inline keyboard 確認/取消/查看分析）
- 引入 Shioaji（永豐金）Python API 作為主要券商底層
- 新增 BrokerBase 抽象層，SinopacBroker 與 YuantaBroker 同時實作
- SSE 行情串流改接 Shioaji Tick 訂閱
- StopLossGuard 補全為雙層完整版（Layer1 委託 + Layer2 輪詢）
- 前端新增兩段式下單確認 UI 與環境徽章（模擬黃 / 正式紅）
- 三級快取套用至 quote、indicators、chip 三個 endpoint（23.8s → 0.006s）
- K 線形態識別 27 種加入 indicators API 回應
- AI Self Audit 自審計：記錄預測 → 事後比對準確率
- 主力意圖四階段分析（吸籌 / 拉抬 / 出貨 / 打壓）

## Capabilities

### New Capabilities

- `pine-script-alert`: TradingView Pine Script Alert 格式檔（.pine），可直接匯入 TV 使用
- `reentry-evaluation`: 重複信號 ReEntry 評估引擎，三種決策（加碼/忽略/警示）
- `telegram-interactive`: Telegram Bot inline keyboard 雙向互動（確認/取消/查看分析）
- `broker-base`: BrokerBase 抽象類別 + SinopacBroker（Shioaji）+ YuantaBroker 重構
- `shioaji-sse-stream`: Shioaji Tick 訂閱 → SSE 串流 → 前端 useSignalStream
- `stop-loss-guard-v2`: StopLossGuard 完整雙層版（Layer1 委託 + Layer2 輪詢）
- `order-confirm-ui`: 兩段式下單確認彈窗 + 環境徽章（模擬/正式）
- `three-tier-cache`: L1 記憶體 / L2 Redis / L3 SQLite 三級快取
- `candlestick-patterns`: 27 種 K 線形態識別，加入 indicators API
- `ai-self-audit`: AI 預測記錄 + 事後準確率自審計報表
- `market-maker-intent`: 主力意圖四階段分析（台股籌碼版）

### Modified Capabilities

- `stop-loss-guard`: 現有基礎版升級為雙層完整版（行為變更）
- `sse-stream`: 行情來源從 Redis Pub/Sub 改為 Shioaji Tick（介面不變）

## Impact

- **後端新增**：`backend/brokers/base.py`、`backend/brokers/sinopac.py`、`backend/services/cache.py`、`backend/services/candlestick.py`、`backend/services/audit.py`、`backend/routers/audit.py`
- **後端修改**：`backend/agents/stop_loss_guard.py`、`backend/routers/stream.py`、`backend/routers/webhook.py`、`backend/utils/telegram.py`、`backend/services/stock_quote_fetcher.py`
- **前端新增**：`frontend/components/OrderConfirmModal.tsx`、`frontend/components/EnvBadge.tsx`
- **前端修改**：`frontend/hooks/useSignalStream.ts`、`frontend/app/stock/page.tsx`
- **新增依賴**：`shioaji`（永豐金 SDK）、`python-telegram-bot>=20`（支援 inline keyboard）
- **資料庫**：新增 `ai_audit` 表（記錄 AI 預測 + 實際結果）
- **文件**：新增 `tradingview/alert_strategy.pine`
