## Context

台股AI雷達目前券商層綁定元大（Yuanta），無抽象介面；行情串流依賴 TWSE MIS 輪詢（延遲高）；缺少重複信號評估、Telegram 互動、三級快取、K 線形態識別、AI 自審計、主力意圖分析等功能。本次設計涵蓋 Shioaji Pro（永豐金）整合與 4 項補漏功能，共 13 個子系統。

## Goals / Non-Goals

**Goals:**
- 定義 BrokerBase 抽象層，讓券商可熱插拔
- 用 Shioaji 即時 Tick 取代輪詢行情，降低延遲至 < 100ms
- 完整雙層停損保護（委託 + 輪詢備援）
- 三級快取讓 API 響應從 23.8s 降至 0.006s（熱路徑）
- 27 種 K 線形態識別整合入 indicators API
- AI 預測自審計，每日自動計算準確率
- 主力意圖四階段分析加入每股分析結果

**Non-Goals:**
- 不支援多帳戶並發下單
- 不實作 Shioaji 期貨/選擇權下單（僅現股）
- 不移除元大 Yuanta 整合（保留並列）

## Decisions

### D1：BrokerBase 設計為 ABC（抽象基類）
採用 Python `abc.ABC`，定義 `place_order`、`cancel_order`、`get_positions`、`subscribe_tick` 四個抽象方法。
- 選 ABC 而非 Protocol：ABC 在 runtime 強制實作，避免遺漏方法時靜默失敗。
- `SinopacBroker`（Shioaji）為預設 active broker；`YuantaBroker` 保留作備援。
- 切換券商透過環境變數 `BROKER=sinopac|yuanta`，main.py 啟動時注入。

### D2：三級快取實作為統一 CacheService
```
L1（記憶體 dict）→ L2（Redis）→ L3（SQLite）→ 原始 API
```
- L1 TTL 5s（單進程熱資料），L2 TTL 60s（跨 worker），L3 TTL 300s（持久化）
- 統一 `get(key)` / `set(key, value, ttl)` 介面，呼叫端無感知快取層
- 回寫策略：L3 miss 後，從 API 取得資料同時寫入 L1+L2+L3

### D3：K 線形態識別用純 Python 實作（不依賴 TA-Lib）
TA-Lib 在 Windows/ARM 環境安裝困難。改以純 Python 邏輯實作 27 種形態，僅依賴 numpy。形態識別結果加入 `GET /api/stock/{symbol}/indicators` 回應的 `patterns` 欄位。

### D4：Telegram 互動用 python-telegram-bot v20 async
- 升級至 v20（async 原生），使用 `InlineKeyboardMarkup` + `CallbackQueryHandler`
- 收到 webhook 信號後推播含三個按鈕的訊息：[✅確認下單] [❌取消] [🔍查看分析]
- Bot 以 polling 模式運行（避免需要 public URL）

### D5：主力意圖使用籌碼 + 技術指標規則引擎
四階段判斷為規則式（非 ML），輸入為現有 `chip` 資料 + `indicators`：
- 吸籌：TDCC 集中度連升 3 日 AND 量比 < 0.8
- 拉抬：收盤 > MA20 AND（外資買超 OR 投信買超）AND 量比 > 1.5
- 出貨：高檔連縮量（量比 < 0.7）AND 籌碼分散（TDCC 集中度下降）
- 打壓：連續 2 日以上跌停 OR 外資連賣 5 日以上

## Risks / Trade-offs

- **Shioaji 帳號依賴** → 未登入時自動 fallback 到 TWSE MIS 輪詢（降級模式）
- **三級快取複雜度增加** → CacheService 封裝後呼叫端透明，單元測試 mock L1 即可
- **27 種形態純 Python 效能** → 形態識別結果納入 L2 Redis 快取，不每次重算
- **Telegram polling 與 FastAPI 共存** → 用 asyncio background task 跑 bot loop，不阻塞主進程

## Migration Plan

1. 新增 BrokerBase + SinopacBroker，預設 `BROKER=sinopac`（但 Shioaji 帳號未設定時 fallback yuanta）
2. 部署 CacheService，各 endpoint 逐一接入（quote → indicators → chip）
3. Telegram Bot 升級，舊 `send_message` 介面保持相容
4. K 線形態識別加入 indicators response（新增欄位，不 breaking）
5. AI Audit 表建立後台排程（每日 15:30 比對當日收盤）

## Open Questions

- Shioaji API key 由使用者自行提供，需要在 `.env.prod.example` 加入 `SINOPAC_ACCOUNT` / `SINOPAC_PASSWORD` 說明
- Pine Script 檔是否需要同時支援 TV Webhook 送到 ngrok（開發）和正式 HTTPS endpoint？
