## Context

台股AI雷達在 Change-H 後已具備完整的 AI 分析核心（K線形態、主力意圖、自審計）與元大券商下單流程。本 Change 在不動核心架構的前提下，補齊五個實用缺口：財報日曆、通知中心、選股進階篩選、RWD 修正、以及永豐（Sinopac/Shioaji）券商實作。

架構不變：FastAPI 後端 + Next.js 前端 + SQLite DB + APScheduler 定時任務。

## Goals / Non-Goals

**Goals:**
- 財報日曆：FinMind API 取得除息/除權/法說日期，每日 08:00 更新，前端月曆視圖
- 通知中心：每次 Telegram 訊息發送時同步寫入 DB，前端列表頁含已讀標記
- 選股進階篩選：`/screener` 加入 patterns 與 market_maker_intent.phase 作為篩選條件
- RWD 修正：`/stock`、`/screener`、`/portfolio` 在 < 768px 解決溢出與表格問題
- 永豐券商：完整實作 `SinopacBroker`（place_order/cancel_order/get_positions），設定頁切換券商

**Non-Goals:**
- 不新增 AI 模型或推論邏輯
- 不改動 Webhook / RiskManager 核心流程
- 不實作永豐模擬帳戶自動化測試（需實體帳號，人工驗證）

## Decisions

**D1 — 財報日曆資料源選 FinMind**
FinMind 已整合於現有籌碼服務，直接重用 `fetch_finmind()`；不另外引入 twstock 或爬蟲，避免依賴膨脹。資料快取於 SQLite `earnings_calendar` 表，TTL 1 天。

**D2 — 通知中心寫入點在 `utils/telegram.py`**
`send_message()` 是唯一的 Telegram 發送入口，在此處加入 DB 寫入最省事，不需改動各呼叫方。`notifications` 表結構：`id / message / source / created_at / is_read`。

**D3 — 選股篩選條件以後端 filter 實作**
`GET /api/screener/scan` 現有的 factor 過濾流程，直接在 Python 端加入 `patterns` 與 `phase` 條件比對，不在前端過濾，確保一致性。

**D4 — RWD 修正以 inline style breakpoint 為主**
現有頁面使用 inline style，保持一致；僅在必要處用 `isMobile` hook 切換 grid columns，不引入 CSS module 或 Tailwind class。

**D5 — SinopacBroker 採 shioaji 套件**
`shioaji` 是永豐官方 Python SDK，`backend/brokers/sinopac.py` 已建骨架；本 Change 補完三個核心方法。券商切換透過環境變數 `DEFAULT_BROKER=sinopac|yuanta`。

## Risks / Trade-offs

- `shioaji` 需要實體永豐帳號才能完整測試 → 後端邏輯可 mock，整合測試標記為手動
- FinMind 免費 API 有頻率限制（每分鐘 30 次）→ 財報日曆資料每日一次批次更新，不即時查詢
- 通知中心 DB 若無清理機制會無限增長 → 加入保留最近 1000 筆的清理邏輯（APScheduler 每週執行）

## Migration Plan

1. 執行 `schema_sqlite.sql` 新增 `earnings_calendar` 與 `notifications` 兩張表（`CREATE TABLE IF NOT EXISTS`，無破壞性）
2. 重啟後端服務，APScheduler 在 08:00 自動首次拉取財報日曆
3. 前端 `next dev` 無需額外設定
4. 永豐切換：設定 `.env` 中 `DEFAULT_BROKER=sinopac` 並填入 Shioaji 帳密後重啟
