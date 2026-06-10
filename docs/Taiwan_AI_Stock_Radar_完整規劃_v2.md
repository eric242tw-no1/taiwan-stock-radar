# Taiwan AI Stock Radar — 完整規劃文件

> 版本：v2.0  
> 更新日期：2026-06-04  
> 硬體環境：Asus Flow Z13（i9-12900H + RTX 3050 Ti + 16GB RAM）  
> 開發方式：零基礎，Hermes Agent 主導執行  
> 參考來源：PRD v1.0 + 優化增補 v1.1 + 宏觀連動表 + 大戶集保表 + Hermes 擴充指令

---

## 一、專案願景

打造一個台股專用的 AI 投資決策平台，整合：

- **Bloomberg 風格** — 市場總覽、美股連動、資金動向、產業輪動
- **TradingView 風格** — K 線圖表、技術指標、信號回傳
- **Finviz 風格** — 台股 + 美股科技雙熱力圖、個股篩選
- **對沖基金級量化** — ATR、滾動 Beta、大戶集保、宏觀連動係數
- **AI 決策中心** — Claude API 綜合分析、買賣評分、風險提示

交易風格定位：**波段操作**（持股數天到數週），由 AI 輔助信號判斷，人工做最終決策。

---

## 二、設備規劃

### 現有設備

| 設備 | 規格 | 用途 |
|------|------|------|
| Asus Flow Z13 | i9-12900H / RTX 3050 Ti / 16GB RAM | 主力開發機、看盤 |
| 硬碟櫃（已購） | 外接儲存 | 歷史行情資料、DB 備份 |

### 建議追加（依優先順序）

| 優先級 | 設備 | 預算 | 用途 | 時機 |
|------|------|------|------|------|
| 🔴 必要 | 迷你主機 或 Raspberry Pi 5 | NT$3,000–15,000 | 24 小時常駐 Agent 自動下單 | Phase 3 前購入 |
| 🟡 建議 | 外接 27" 螢幕 | NT$4,000–8,000 | 雙視窗開發效率 | 開發期間 |
| 🟢 按需 | VPS 雲端主機 | NT$300–500/月 | 常駐備援或測試環境 | Phase 2 後 |

> **注意**：Flow Z13 RAM 焊死無法升級。後端採 Pre-aggregation 架構，API 只做 SELECT，保護 16GB 記憶體上限。

---

## 三、技術堆疊（最終版）

```
前端：Next.js 15 + TypeScript + TailwindCSS + ShadCN UI
後端：FastAPI + SQLAlchemy + Pydantic
資料庫：PostgreSQL
快取：Redis
資料來源：TWSE + FinMind + Yahoo Finance + 期交所 + TDCC（集保）
AI 引擎：Claude API（claude-sonnet-4）
K 線圖：TradingView Lightweight Charts Widget
量化計算：pandas-ta（ATR、Beta、技術指標預算）
部署：Docker Compose
通知：Telegram Bot
版控：GitHub
開發工具：Hermes Agent（自動化建置）
PWA：next-pwa（安卓 APP 打包）
```

---

## 四、系統架構

```
使用者瀏覽器 / 安卓 PWA
    ↓
Next.js 15 前端（雙頁切換 Dashboard）
    ↓
FastAPI 後端（REST API + WebSocket）
    ↓
Redis（即時快取 + Claude API 結果快取）
    ↓
PostgreSQL（所有歷史與預算資料）
    ↓
Data Agents（定時排程）
    ├── 每日 14:30 — TWSE 行情 + 籌碼 + 期貨
    ├── 每日 15:30 — pandas-ta 預算所有指標寫入 stock_indicators_daily
    ├── 每日 16:00 — 宏觀連動係數計算寫入 macro_correlation
    ├── 每週六 — TDCC 大戶集保資料更新 large_holders_weekly
    └── 即時    — WebSocket 推播大盤指數
    ↓
資料來源：TWSE / FinMind / Yahoo Finance / 期交所 / TDCC
```

---

## 五、雙頁儀表板佈局（v3）

### 第一頁：市場總覽（早盤前掌握全局）

```
┌─ Topbar：搜尋 │ 加權/OTC/大台期/S&P500/Nasdaq/道瓊 │ 即時時間 ─┐
├─ [市場總覽] [個股分析] 切換按鈕 ──────────────────────────────┤
│                                                                │
│ ── 🇹🇼 台股市場 ──────────────────────────────────────────── │
│ [市場溫度+廣度]  [台股產業熱力圖]  [產業輪動+八大官股]           │
│                                                                │
│ ── 🇺🇸 美股市場 ──────────────────────────────────────────── │
│ [美股三大指數]   [美股科技熱力圖]  [台美連動分析]                │
│  S&P/Nasdaq/道瓊  NVDA/AMD/TSMC    費半相關/ADR/匯率           │
│                                                                │
│ ── 📊 個股動向 ──────────────────────────────────────────── │
│ [波段領頭羊]     [個股排行榜]      [市場快訊 AI 摘要]            │
│  創60日高/鎖漲停  漲/跌/量切換     點擊 → AI 深度總覽            │
└────────────────────────────────────────────────────────────┘
```

### 第二頁：個股分析（盤中主力工作頁）

```
┌─ Topbar（同上）────────────────────────────────────────────┐
├─ [市場總覽] [個股分析] 切換按鈕 ──────────────────────────────┤
│                                                                │
│  股票名稱 現價 漲跌幅  │  [AI 決策中心]                         │
│  [1D 5D 1M 3M 切換]   │   綜合評分 87/100                      │
│  [重要事件倒數]        │   正面/風險因素                         │
│   法說 3天/除息 12天   │   ATR波動風險 / Beta連動性              │
│   期指結算 18天 ⚠️     │   大戶集保趨勢                          │
│  [K 線圖 TradingView] │  [TradingView 信號模組]                 │
│  [成交量]             │   AI 替代 / Webhook 預留                │
│  [技術指標 6格]        │                                        │
│   RSI/MACD/KD/布林    │                                        │
│   VWAP/MA排列         │                                        │
├─────────────────────────────────────────────────────────┤
│  [籌碼分析]            │  [衍生商品]            │  [乖離率]      │
│   三大法人             │   外資期貨淨部位        │   MA20 +12.3% │
│   融資融券             │   PCR / 未平倉         │   歷史百分位   │
│   借券趨勢             │   選擇權支撐壓力        │   89th 過熱   │
│   券商分點 Top5        │   期指結算倒數 ⚠️       │   MA5/20/60   │
│   集中度 68%           │                        │   均值回歸目標 │
└─────────────────────────────────────────────────────────┘
```

---

## 六、功能模組詳細規格

### 模組 1：台股市場雷達

- **市場溫度計**：0–100 分，整合漲跌家數、成交量、外資動向、官股動向
- **市場廣度**：上漲 / 下跌 / 漲停 / 跌停家數、創 60 日新高家數
- **台股產業熱力圖**：12 大產業依漲跌幅著色（綠/紅色系）
- **產業輪動**：資金流入 / 流出方向圖
- **八大官股買賣超**：合計金額、連續買超天數、撐盤訊號判斷

### 模組 2：美股市場（新增）

- **三大指數**：S&P500 / Nasdaq / 道瓊 昨收漲跌幅
- **輔助指標**：VIX 恐慌指數、費城半導體、美元指數 DXY
- **美股科技熱力圖**：NVDA / AMD / TSMC ADR / MSFT / AVGO / GOOGL / ASML / AMAT / META（藍色系，與台股視覺區分）
- **台美連動面板**：NVDA / 費半 / TSMC ADR 對台股影響，20日滾動相關係數

### 模組 3：個股分析

- **搜尋功能**：輸入股票代號（2330）或名稱（台積電）
- **重要事件倒數面板**（新增）：
  - 法說會倒數天數（黃色警示：≤3天）
  - 除權息日倒數
  - **台指期結算日倒數**（橘色警示：≤5天）⚠️
  - 季報公布截止日
- **K 線圖**：TradingView Widget，支援日 / 週 / 月切換
- **技術指標**：MA5 / MA20 / MA60 / RSI / MACD / KD / VWAP / 布林通道
- **量化風險指標**（新增，Sprint 4）：
  - ATR(14)：絕對波動幅度，協助計算停損距離
  - 滾動 Beta(60日)：與大盤連動性，判斷系統性風險

### 模組 4：乖離率分析

- 20MA 乖離率：當前偏離 %
- 歷史百分位：此乖離率在過去 1 年的位階
- 狀態判斷：過熱（>85%）/ 正常 / 過冷（<15%）
- MA5 / MA20 / MA60 三層乖離率並列
- 均值回歸目標價

### 模組 5：籌碼分析

- **三大法人**：外資 / 投信 / 自營商 每日買賣超（近 20 日走勢）
- **融資融券**：融資餘額變化、融券餘額變化
- **借券趨勢**：借券張數增減、還券張數
- **券商分點 Top5**（新增）：每日買超前五大、賣超前五大分點
- **籌碼集中度**（新增）：前10大買超分點合計占當日成交量比例（5日/20日）
- **大戶集保分佈**（新增，週更）：400張以上 / 1000張以上大戶人數與持股比例趨勢

### 模組 6：期貨與選擇權

- **外資期貨淨部位**：多空方向與數量
- **Put/Call Ratio（PCR）**：市場恐慌/樂觀指標
- **未平倉量**：大台 / 小台 各到期月份
- **選擇權支撐壓力**：依 OI 最大值推算支撐 / 壓力價位
- **台指期結算日倒數**（新增）⚠️：距離當月結算日天數，≤5天自動顯示警示，AI 評分自動加權「結算風險」

### 模組 7：AI 決策中心

Claude API 接收結構化 JSON Context，包含所有指標預算結果：

```json
{
  "symbol": "2330",
  "price_data": { "close": 1082, "ma20_bias": 12.3, "bias_percentile": 89 },
  "technicals": { "rsi": 62.4, "macd": "bullish_cross", "kd": "K71_D65" },
  "risk_metrics": { "atr_14": 28.5, "rolling_beta_60": 1.12 },
  "chip_data": { "foreign_buy": 82, "branch_concentration": 0.68 },
  "large_holders": { "pct_over_400": 42.3, "trend": "increasing" },
  "macro_correlation": { "corr_sox": 0.82, "corr_dxy": -0.61 },
  "calendar_events": {
    "earnings_call_days": 3,
    "ex_dividend_days": 12,
    "futures_settlement_days": 18
  },
  "gov_stock": { "total_buy": 48.2, "consecutive_days": 3 }
}
```

**輸出格式範例：**
```
【台積電 2330 AI 分析】波段多方，持有。

正面因素：
▲ MACD 黃金交叉（日線）
▲ 外資連續 4 日買超 +82億
▲ 官股連買 3 日 +48億（撐盤訊號）
▲ 券商分點集中度 68%（主力鎖碼）
▲ 大戶 400張以上持股比例上升中

風險因素：
! 乖離率歷史 89 百分位（偏熱，ATR=28.5）
! 法說會倒數 3 天（事件風險）
⚠️ 台指期結算倒數 18 天（留意軋空）
▼ 滾動 Beta=1.12，大盤若回調放大跌幅

買進評分：87 / 100
建議停損：MA20 支撐 964，約 -11%（2.5倍 ATR）
```

### 模組 8：TradingView 信號模組（預留）

- **現階段**：AI 根據 pandas-ta 計算值模擬信號
- **升級後**：TradingView Plus Webhook 接收 Pine Script 即時信號

---

## 七、資料庫設計（完整版）

### stocks（股票基本資料）
```sql
id        SERIAL PRIMARY KEY
symbol    VARCHAR(10)
name      VARCHAR(50)
industry  VARCHAR(50)
```

### daily_price（每日行情）
```sql
symbol    VARCHAR(10)
date      DATE
open      NUMERIC
high      NUMERIC
low       NUMERIC
close     NUMERIC
volume    BIGINT
```

### chip_data（籌碼資料）
```sql
symbol          VARCHAR(10)
date            DATE
foreign_buy     BIGINT
investment_buy  BIGINT
dealer_buy      BIGINT
margin          BIGINT
short_interest  BIGINT
borrow_shares   BIGINT    -- 借券張數
return_shares   BIGINT    -- 還券張數
```

### futures_data（期貨選擇權）
```sql
date                 DATE
foreign_net_position BIGINT
pcr                  NUMERIC
open_interest        BIGINT
settlement_date      DATE    -- 當月結算日（新增）
days_to_settlement   INT     -- 距結算天數（新增）
```

### stock_indicators_daily（預算指標表，每日收盤後寫入）
```sql
symbol          VARCHAR(10)
date            DATE
ma20_bias       NUMERIC    -- 20MA 乖離率
bias_percentile NUMERIC    -- 乖離率歷史百分位
is_overheat     BOOLEAN    -- 是否過熱
atr_14          NUMERIC    -- 14日 ATR 絕對波動值（新增）
rolling_beta_60 NUMERIC    -- 60日滾動 Beta（新增）
rsi_14          NUMERIC
macd_signal     VARCHAR(20)
kd_k            NUMERIC
kd_d            NUMERIC
```

### macro_correlation（全球宏觀連動表，新增）
```sql
symbol     VARCHAR(10)
date       DATE
corr_sox   NUMERIC    -- 與費城半導體相關係數（20日滾動）
corr_scfi  NUMERIC    -- 與 SCFI 運價指數相關係數（航運類股）
corr_dxy   NUMERIC    -- 與美元指數相關係數
```

### large_holders_weekly（每週大戶集保分佈，新增）
```sql
symbol             VARCHAR(10)
week_end_date      DATE
holders_over_400   INT      -- 400張以上大戶人數
percent_over_400   NUMERIC  -- 400張以上大戶持股比例
holders_over_1000  INT      -- 1000張以上大戶人數
percent_over_1000  NUMERIC  -- 1000張以上大戶持股比例
```

### branch_chip_daily（券商分點資料，新增）
```sql
symbol      VARCHAR(10)
date        DATE
branch_name VARCHAR(50)    -- 分點名稱
buy_volume  BIGINT         -- 買進張數
sell_volume BIGINT         -- 賣出張數
net_volume  BIGINT         -- 淨買超張數
```

### calendar_events（重要行事曆，新增）
```sql
symbol       VARCHAR(10)
event_type   VARCHAR(30)  -- earnings_call / ex_dividend / futures_settlement / report_deadline
event_date   DATE
description  TEXT
```

---

## 八、後端架構防禦設計（16GB RAM 保護）

### 1. Pre-aggregation 原則
所有技術指標（乖離率、ATR、Beta、宏觀連動係數）在每日收盤後由 Data Agent **背景預算完畢**，寫入專用表。前端 API 僅執行 `SELECT`，不做任何即時計算。

### 2. Claude API 快取機制
```python
# 每日收盤後產生一次 AI 報告，快取至 Redis（TTL 至隔日開盤）
def get_ai_analysis(symbol: str):
    cache_key = f"ai:{symbol}:{today}"
    cached = redis.get(cache_key)
    if cached:
        return cached  # 直接回傳，不呼叫 API
    result = call_claude_api(symbol)
    redis.set(cache_key, result, ex=57600)  # 16小時 TTL
    return result
```

### 3. Docker 記憶體限制
```yaml
services:
  fastapi:
    mem_limit: 512m
  postgres:
    mem_limit: 2g
  redis:
    mem_limit: 256m
  data-agent:
    mem_limit: 1g
```

---

## 九、開發路線圖（v2）

### Sprint 1（第 1–2 週）— 環境建置

安裝清單：Docker Desktop、PostgreSQL、DBeaver、VS Code、Git

**Hermes Agent 任務：**
```
1. 建立專案目錄結構
   /taiwan-stock-radar
   ├── frontend/   (Next.js 15)
   ├── backend/    (FastAPI)
   ├── agents/     (Data Agents)
   ├── docker-compose.yml
   └── README.md

2. 初始化 Next.js 15（TailwindCSS + ShadCN UI）
3. 初始化 FastAPI（main.py + /api/health + CORS）
4. 建立 Docker Compose（PostgreSQL + FastAPI + Next.js + Redis）
5. 執行完整 Schema（所有 8 張表）
每步完成後回報並等待確認。
```

---

### Sprint 2（第 2–3 週）— 資料串接 + 量化指標

資料來源：TWSE + FinMind + Yahoo Finance + 期交所 + TDCC

**Hermes Agent 擴充任務（進階）：**
```
1. 建立 FastAPI 後端骨架與 API endpoints
2. 建立每日收盤 Data Agent（14:30 觸發）：
   - TWSE 行情、FinMind 籌碼、期交所期貨選擇權
   - FinMind 券商分點買賣超
3. 建立 pandas-ta 指標預算腳本（15:30 觸發）：
   - 計算 ATR(14)、Rolling Beta(60日)
   - 計算 20MA 乖離率與歷史百分位
   - 所有結果寫入 stock_indicators_daily
4. 建立宏觀連動計算腳本（16:00 觸發）：
   - 計算個股與 SOX（費半）、DXY 的 20日滾動相關係數
   - 寫入 macro_correlation 表
5. 建立每週六 TDCC 爬蟲：
   - 爬取大戶集保分佈資料
   - 寫入 large_holders_weekly 表
6. 建立台指期結算日自動計算：
   - 每月第三個週三 = 結算日
   - 寫入 calendar_events 表
   - 距結算 ≤5天時標記警示
```

---

### Sprint 3（第 3–4 週）— 市場總覽頁（第一頁）

建置項目：
- 台股市場溫度計 + 廣度
- 台股產業熱力圖（12產業）
- 八大官股買賣超
- 美股三大指數 + 輔助指標
- 美股科技熱力圖（9檔）
- 台美連動面板（宏觀相關係數應用）
- 波段領頭羊（創高/鎖漲停）
- 個股排行榜（漲/跌/量）
- 市場快訊 AI 摘要

---

### Sprint 4（第 5–6 週）— 個股分析頁（第二頁）+ AI

建置項目：
- 搜尋股票功能
- 重要事件倒數面板（法說/除息/期指結算/季報）
- TradingView K 線嵌入
- 技術指標面板（含 ATR / Beta）
- 乖離率模組（含歷史百分位）
- 籌碼分析（含券商分點 + 大戶集保）
- 期貨選擇權模組（含結算倒數警示）
- **Claude API 串接**：
  - 組合 JSON Context（所有預算結果）
  - 傳入 AI 決策中心
  - Redis 快取結果（每日一次）

---

### Sprint 5（第 7–8 週）— 整合 + 優化

建置項目：
- 雙頁切換完整整合測試
- TradingView 信號模組（Webhook 預留介面）
- Telegram Bot 推播（AI 信號 + 結算警示）
- next-pwa 設定（安卓 PWA 打包）
- Docker Compose 完整啟動測試
- 手機版面適配（RWD）

---

## 十、開源套件清單

| 功能 | 套件 | 說明 |
|------|------|------|
| K 線圖 | `lightweight-charts` | TradingView 官方開源 |
| 技術指標 | `pandas-ta`（Python） | ATR/RSI/MACD/Beta 全包 |
| 熱力圖 | `recharts` / `d3` | 台股 + 美股雙熱力圖 |
| 資料表格 | `TanStack Table` | 排行榜、籌碼表格 |
| 狀態管理 | `Zustand` | 跨元件股票狀態 |
| API 快取 | `SWR` | 前端自動快取行情 |
| 日期計算 | `dayjs` | 交易日、結算日計算 |
| PWA 打包 | `next-pwa` | 一鍵轉安卓 APP |
| 通知 | `react-hot-toast` | 即時信號提示 |

---

## 十一、費用估算

### API 費用

| 項目 | 費用 | 說明 |
|------|------|------|
| Claude API | NT$180–240 / 月 | 每日 50 次，Redis 快取後大幅降低 |
| FinMind API | 免費 / NT$300+ | 基本免費，高頻需付費方案 |
| TradingView Widget | 免費 | 嵌入版免費使用 |
| TradingView Plus（未來） | $24.95 / 月 | Webhook 升級後才需要 |

### 硬體費用

| 項目 | 預算 | 說明 |
|------|------|------|
| 迷你主機（Phase 3 常駐） | NT$8,000–15,000 | 或 Raspberry Pi 5 NT$3,000 |
| VPS 雲端備援（可選） | NT$300–500 / 月 | DigitalOcean / Vultr |

---

## 十二、三階段目標

### Phase 1（MVP，6–8 週）— 看盤 + AI 信號 ✅ 現在開始
人工看 AI 建議，手動下單。系統提供完整分析依據，包含對沖基金級量化指標。

### Phase 2（+2 個月）— 半自動下單
- 串接元大 API（需本人申請憑證）
- 手機確認一鍵下單介面
- Telegram 即時推播（AI 信號 + 台指期結算警示）
- 部位追蹤、損益顯示
- 風控：每筆最大損失 2%，停損距離參考 ATR(14)

### Phase 3（+2 個月）— Hermes Agent 全自動
- Hermes Agent 完整 Tool Use 架構
- 24 小時常駐主機運行
- Agent 自主監控、下單、停損
- 每週績效報告自動生成
- **條件**：Phase 2 穩定運行至少 1 個月後才進入

---

## 十三、注意事項與風險

| 風險 | 說明 | 對策 |
|------|------|------|
| 元大 API 申請 | 需本人至券商辦理，Agent 無法代勞 | Phase 2 前提早申請 |
| FinMind 免費額度 | 高頻呼叫可能超限 | Redis 快取 + Pre-aggregation |
| Flow Z13 RAM 限制 | 16GB 無法升級 | Docker 容器限制記憶體用量 |
| TradingView Webhook | 需升級 Plus 方案 | Phase 1 先用 AI 替代 |
| 台指期結算風險 | 結算週行情波動放大 | 系統自動標記警示，AI 評分加權 |
| TDCC 爬蟲穩定性 | 集保資料為週更，格式可能變動 | 加入錯誤通知，人工確認 |
| 自動下單風險 | Phase 3 涉及真實資金 | 先用模擬帳戶測試 1 個月 |

---

## 十四、Hermes Agent Sprint 2 完整擴充指令

```
你是一個後端量化系統開發 Agent，目標是擴充 Taiwan AI Stock Radar 的資料層。

Sprint 2 任務（依序執行）：

【任務一：FastAPI 後端骨架】
1. 建立 /api/stock/{symbol} 端點（回傳所有預算指標）
2. 建立 /api/market/overview 端點（市場溫度、廣度、官股）
3. 建立 /api/market/us 端點（美股指數、科技熱力）
4. 設定 WebSocket /ws/index（推播大盤即時指數）

【任務二：每日收盤 Data Agent（14:30）】
1. 爬取 TWSE 每日行情 → daily_price
2. FinMind 三大法人 → chip_data
3. FinMind 融資融券借券 → chip_data
4. FinMind 券商分點買賣超 → branch_chip_daily
5. 期交所期貨選擇權 → futures_data
6. 自動計算當月台指期結算日（第三個週三）→ calendar_events

【任務三：指標預算腳本（15:30）】
使用 pandas-ta 計算以下指標，寫入 stock_indicators_daily：
- ATR(14)：14日平均真實波幅
- Rolling Beta(60日)：與加權指數的滾動相關 Beta
- RSI(14)、MACD signal、KD 值
- 20MA 乖離率 + 歷史百分位（近252交易日）

【任務四：宏觀連動腳本（16:00）】
- 計算個股與 SOX（費半 ^SOX）的 20日滾動相關係數
- 計算個股與 DXY（美元指數）的 20日滾動相關係數
- 航運類股額外計算與 SCFI 的相關係數
- 全部寫入 macro_correlation 表

【任務五：每週六 TDCC 大戶集保爬蟲】
- 爬取台灣集保結算所大戶持股分佈
- 解析 400張以上、1000張以上人數與比例
- 寫入 large_holders_weekly 表

【任務六：Claude API Context 組合器】
建立 build_ai_context(symbol) 函數，從各表 SELECT 資料，
組合成結構化 JSON，作為 Claude API system context 傳入。
結果快取至 Redis，TTL = 到隔日 09:00。

每完成一個任務，回報測試結果並等待確認後再繼續。
```

---

*文件由 Claude（Anthropic）根據完整討論內容整合生成*  
*v2.0 新增：美股模組、對沖基金量化指標、宏觀連動、大戶集保、台指期結算警示、完整 Hermes Sprint 2 指令*

---

## 十五、回測模組（新增）

### 定位
幫助你在真實下單前，先驗證策略的歷史勝率。放在**第三頁「策略回測」**，或個股分析頁的側邊抽屜。

### 技術選型
```
回測引擎：Backtrader（Python，免費開源）
資料來源：直接從 PostgreSQL daily_price 表讀取
觸發方式：手動設定條件後執行，非即時
```

### 使用流程
```
1. 選擇股票（2330）
2. 設定回測期間（2020-01-01 ~ 2025-12-31）
3. 設定進場條件（可多選）：
   - MACD 黃金交叉
   - 外資連買 N 日
   - 乖離率 < X%
   - 籌碼集中度 > Y%
4. 設定出場條件：
   - 停利 +15%
   - 停損 −7%（或 2.5倍 ATR）
   - 持有超過 N 天
5. 執行回測 → 輸出報告
```

### 輸出報告格式
```
【2330 台積電 回測報告】
期間：2020-01-01 ~ 2025-12-31

總交易次數：48 次
勝率：62.5%（30勝 18負）
總報酬率：+187.3%
年化報酬率：+24.8%
最大回撤：−18.2%
平均持有天數：12.4 天
最佳單筆：+31.4%
最差單筆：−12.8%

逐筆明細：
進場日      出場日      報酬
2024-01-15  2024-02-02  +8.4%
2024-03-22  2024-04-10  −5.1%
...
```

### 資料庫新增表
```sql
-- 回測策略表
backtest_strategies (
  id           SERIAL PRIMARY KEY,
  name         VARCHAR(50),
  conditions   JSONB,     -- 進出場條件
  created_at   TIMESTAMP
)

-- 回測結果表
backtest_results (
  id            SERIAL PRIMARY KEY,
  strategy_id   INT,
  symbol        VARCHAR(10),
  period_start  DATE,
  period_end    DATE,
  win_rate      NUMERIC,
  total_return  NUMERIC,
  max_drawdown  NUMERIC,
  trades        JSONB,    -- 逐筆交易明細
  created_at    TIMESTAMP
)
```

### Sprint 規劃
回測模組列為 **Sprint 6**（MVP 完成後獨立開發），不影響 Phase 1 主線進度。

---

## 十六、事件風險行事曆（擴充）

### 涵蓋事件類型

| 事件 | 時間規律 | 影響特性 | 警示天數 |
|------|------|------|------|
| **每月營收公布** | 每月 10 日前（假日順延）| 個股短線震盪，提前反應 | ≤5天 🟡 |
| **季報公布** | 3/31、5/15、8/14、11/14 | 波段方向確立 | ≤7天 🟠 |
| **法說會** | 各公司自訂 | 市場預期重新定價 | ≤3天 🔴 |
| **台指期結算** | 每月第三個週三 | 大盤波動放大、軋空風險 | ≤5天 🟠 |
| **除權息旺季** | 7–9 月各公司自訂 | 填息/貼息行情 | ≤5天 🟡 |
| **聯準會 FOMC** | 每年 8 次固定日期 | 影響外資動向與匯率 | ≤3天 🔴 |
| **台灣央行理監事會** | 每季一次 | 影響匯率與金融股 | ≤3天 🔴 |

### AI 整合：事件風險密度評分

Claude API 收到 `calendar_events` 後，自動計算「未來 10 日事件風險密度」並輸出建議：

```
【事件風險評估 — 台積電 2330】

未來 10 日風險密度：高 ⚠️

距離每月營收公布：5 天
  歷史平均震盪：±3.2%（近12次統計）
  規律：公布前 2–3 天往往提前反應

距離季報公布：23 天（風險較低）

距離台指期結算：18 天（中度影響，Beta=1.12）

FOMC 會議：下次 6/18（結算同日，雙重風險）

AI 建議：
  事件風險密度：中偏高
  建議部位控制在 6–7 成
  營收公布前 2 天考慮減碼一半
  停損參考：2.5倍 ATR = 71元（目標 1,011）
```

### 資料庫調整（calendar_events 擴充）
```sql
calendar_events (
  id           SERIAL PRIMARY KEY,
  symbol       VARCHAR(10),    -- 個股事件用股票代號；大盤事件填 'MARKET'
  event_type   VARCHAR(30),    -- monthly_revenue / quarterly_report /
                               -- earnings_call / futures_settlement /
                               -- ex_dividend / fomc / cbc_meeting
  event_date   DATE,
  description  TEXT,
  alert_days   INT,            -- 幾天前開始警示
  alert_level  VARCHAR(10),    -- low / medium / high
  hist_avg_chg NUMERIC         -- 歷史平均震盪幅度（%）
)
```

### 自動填入規則（Hermes Sprint 2 擴充）
```python
# 每月自動計算並寫入：
# 1. 台指期結算日（第三個週三）
# 2. 每月 10 日營收公布（假日順延）
# 3. FOMC 日期（從 Fed 官網爬取年度行事曆）
# 4. 個股法說會、除息日（從 TWSE 公告爬取）
```


---

## 十七、左側導覽列設計

參考 DSA 介面設計，系統改為**左側固定導覽列 + 主內容區**的版面架構。

### 導覽列結構

```
┌──────────────────┐
│  🟢 台股AI雷達    │  Logo + 狀態
├──────────────────┤
│  🏠 市場總覽      │  第一頁（台股+美股）
│  📈 個股分析      │  第二頁（K線+AI決策）
│  🔄 選股工作流    │  第三頁（因子掃描+自選池）
│  💼 持倉追蹤      │  第四頁（損益+部位）
│  📊 回測          │  第五頁（策略驗證）
│  🔔 警報設定      │  第六頁（條件設定）
├──────────────────┤
│  ⚙️ 設定          │  API金鑰、資料來源
│  🌙 主題          │  深色/淺色切換
└──────────────────┘
```

### 分析記錄側邊欄（個股分析頁專屬）

個股分析頁左側附加一個可收合的分析記錄清單，每次查詢後自動寫入：

```
┌─────────────────────┐
│ 📋 分析記錄          │
├─────────────────────┤
│ ■ 台積電 2330        │
│   持有 87分          │
│   06/04 15:30       │
├─────────────────────┤
│ □ 聯發科 2454        │
│   觀望 62分          │
│   06/04 14:20       │
├─────────────────────┤
│ □ 鴻海 2317          │
│   減倉 41分          │
│   06/03 16:10       │
└─────────────────────┘
```

評分顏色規則：
- 80分以上 → 綠色「持有/買進」
- 50-79分 → 黃色「觀望」
- 50分以下 → 紅色「減倉/賣出」

### 資料庫新增表

```sql
-- 分析記錄表
analysis_history (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10),
    name        VARCHAR(50),
    ai_score    INT,            -- AI 評分 0-100
    suggestion  VARCHAR(20),    -- 持有/觀望/減倉/買進/賣出
    ai_summary  TEXT,           -- AI 分析摘要
    created_at  TIMESTAMP DEFAULT NOW()
)
```

---

## 十八、選股工作流（三層架構）

### 設計理念

參考量化交易最佳實踐：
> 「因子模型干粗活（全市場選股），AI 系統干細活（深度分析單股），人做決策。」
> 「沒有完美的系統，關鍵是你願意為每個決策花多少時間。」

**三層分工：**
```
第一層：因子模型（全市場掃描）
  → 自動篩選，每日收盤後跑
  → 從 1,800+ 檔台股縮減到 20-30 檔候選

第二層：自選股池（8-10 檔）
  → 你從候選清單手動挑選
  → 每日自動深度分析，給操作建議和狙擊點位

第三層：你做最終決策
  → 看 AI 報告，決定買賣
  → Phase 3 後由 Hermes 自動執行
```

### 第一層：因子模型選股條件（台股版）

**量化篩選（自動，去掉明顯不合格）**

| 因子 | 條件 | 說明 |
|------|------|------|
| 流動性 | 日均成交額 > 3億 | 避免買不到賣不掉 |
| 趨勢方向 | 股價 > MA60 | 只看多頭結構 |
| 短期動能 | 20日漲幅 > 0% | 排除下跌股 |
| 法人認同 | 外資近5日淨買超 | 有法人撐腰 |
| 波動控制 | ATR/股價 < 8% | 排除過度投機股 |
| 籌碼健康 | 融資增幅 < 20% | 避免融資爆倉股 |

**AI 評分排序（選出前 20-30 檔）**

| 因子 | 權重 |
|------|------|
| 技術面綜合分（RSI/MACD/KD/布林）| 30% |
| 籌碼集中度（券商分點）| 25% |
| 法人動向（外資+官股+投信）| 20% |
| 乖離率位階（歷史百分位）| 15% |
| 事件風險扣分（法說/結算/營收）| -10% |

### 第二層：自選股池管理

每日收盤後，系統自動對自選股池中每一檔產生：

```
【每日 AI 報告 — 台積電 2330】
更新時間：2026/06/04 16:00

操作建議：持有
AI 評分：87 / 100

狙擊點位：
  理想買入：回測 1,041（MA20）
  次優買入：回測 1,058（昨收）
  止損位：1,010（跌破 MA20 出場）
  止盈目標：1,150（前高）

今日重點：
  ✅ 外資買超 +82億（連4日）
  ✅ 官股護盤 +48億（連3日）
  ⚠️ 乖離率 89 百分位（偏熱）
  ⚠️ 法說會倒數 3 天

明日關注：法說會前市場預期操作
```

### 第三層：工作時間規劃

**Phase 1（現在）— 每天約 20-30 分鐘**

```
早上開盤前 8:30-9:00：
  □ 看市場總覽（美股昨收 + 台股期指）→ 5分鐘
  □ 看因子掃描候選清單 → 5分鐘
  □ 更新自選股池（加入/移除）→ 5分鐘
  □ 看自選股 AI 報告 → 10分鐘

盤中隨時：
  □ 個股分析頁確認進出場點位

收盤後 14:00：
  □ 看當日 AI 總結報告 → 5分鐘
  □ 決定明日操作方向 → 5分鐘
```

**Phase 2（半自動）— 每天約 10 分鐘**
```
收盤後收到 Telegram 推播
確認 AI 建議 → 手機一鍵確認下單
```

**Phase 3（全自動）— 每天約 5 分鐘**
```
早上看 AI 週報摘要
異常警報才需要手動介入
Hermes Agent 自主執行下單/停損
```

### 新增資料表

```sql
-- 因子掃描結果表
factor_scan_daily (
    symbol          VARCHAR(10),
    date            DATE,
    liquidity_ok    BOOLEAN,
    trend_ok        BOOLEAN,
    momentum_ok     BOOLEAN,
    chip_ok         BOOLEAN,
    factor_score    NUMERIC,    -- 綜合因子分數
    PRIMARY KEY (symbol, date)
)

-- 自選股池
watchlist (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10),
    name        VARCHAR(50),
    added_date  DATE,
    note        TEXT,           -- 加入原因備註
    is_active   BOOLEAN DEFAULT TRUE
)

-- 每日 AI 報告
daily_ai_report (
    symbol          VARCHAR(10),
    date            DATE,
    ai_score        INT,
    suggestion      VARCHAR(20),
    entry_ideal     NUMERIC,    -- 理想買入價
    entry_secondary NUMERIC,    -- 次優買入價
    stop_loss       NUMERIC,    -- 止損位
    take_profit     NUMERIC,    -- 止盈目標
    summary         TEXT,       -- AI 分析摘要
    key_points      JSONB,      -- 重點列表
    cached_at       TIMESTAMP,
    PRIMARY KEY (symbol, date)
)
```

### 系統流程時序

```
每日 14:30 收盤後：
  Step 1 → Data Agent 爬取行情+籌碼+期貨
  Step 2 → pandas-ta 計算所有技術指標
  Step 3 → 因子模型掃描全市場，寫入 factor_scan_daily
  Step 4 → 對自選股池每檔呼叫 Claude API
            （若 Redis 有當日快取則跳過）
  Step 5 → 結果寫入 daily_ai_report
  Step 6 → Telegram Bot 推播每日報告摘要
  Step 7 → 分析記錄寫入 analysis_history

每週六：
  → TDCC 大戶集保資料更新
  → 週報生成（自選股池整週表現摘要）
```


---

## 十九、量化交易策略模組

### 策略總覽與適合度

| 策略 | 適合度 | 階段 | 原因 |
|------|------|------|------|
| 技術分析 | ⭐⭐⭐⭐⭐ | Phase 1 | 已在規劃中，波段操作核心 |
| 事件驅動 | ⭐⭐⭐⭐ | Phase 1 | 行事曆已規劃，法說/營收/結算 |
| 趨勢策略 | ⭐⭐⭐⭐ | Phase 1 | 順勢交易，配合因子模型可做 |
| 多/空策略 | ⭐⭐ | Phase 3 | 需融券，台股限制多 |
| 市場中性 | ⭐⭐ | Phase 3 | Beta 對沖複雜，資金要求高 |
| 配對對沖 | ⭐⭐ | Phase 3 | 需大量歷史資料與相關性計算 |
| 高頻交易 | ❌ | 不適合 | 需專業硬體+極低延遲，個人投資者不適用 |

**Phase 1–2 專注：技術分析 + 事件驅動 + 趨勢策略**
**Phase 3 後評估：多空策略 + 市場中性 + 配對對沖**

---

### 策略選擇器設計

在「選股工作流」頁面加入策略模式切換，切換後因子篩選條件與 AI 評分權重自動調整：

```
┌──────────────────────────────────────────────┐
│  當前策略模式                                   │
│  ● 波段技術分析  ○ 事件驅動  ○ 趨勢跟隨        │
│  ○ 配對對沖（Phase 3）                          │
└──────────────────────────────────────────────┘
```

---

### 模式一：波段技術分析（Phase 1 主力）

**策略說明**
結合 MACD、RSI、KD、布林通道等技術指標，搭配籌碼確認，在多頭結構中尋找波段進場點。

**因子篩選條件**
- MA5 > MA20 > MA60（多頭排列）
- MACD 黃金交叉或柱狀體翻正
- 量能放大（今日量 > 5日均量 × 1.2）
- 外資近 5 日淨買超

**AI 評分權重**

| 因子 | 權重 |
|------|------|
| 技術面綜合分 | 40% |
| 籌碼集中度 | 30% |
| 法人動向 | 20% |
| 乖離率位階 | 10% |

**持有週期**：5–20 天
**停損邏輯**：跌破 MA20 或 2.5 倍 ATR

---

### 模式二：事件驅動（Phase 1）

**策略說明**
在特定企業或總體事件發生前後進行交易，利用市場對事件的預期與反應賺取報酬。

**台股適用事件類型**

| 事件 | 操作方向 | 歷史規律 |
|------|------|------|
| 法說會前 3 天 | 提前佈局多方 | 預期心理推升 |
| 月營收優於預期 | 公布當日做多 | 平均 +3.2% |
| 月營收低於預期 | 公布當日減碼 | 平均 −2.8% |
| 台指期結算週 | 縮減部位 | 波動放大 |
| FOMC 會議前 | 觀望或避險 | 外資動向不確定 |
| 除息前 | 評估填息機率 | 高殖利率股填息率 |

**因子篩選條件**
- 距離重要事件 ≤ 5 天
- 歷史同類事件平均震盪幅度 > 2%
- 技術面不處於明顯下跌趨勢

**AI 評分權重**

| 因子 | 權重 |
|------|------|
| 事件類型與歷史震盪幅度 | 40% |
| 技術面趨勢確認 | 30% |
| 籌碼異動（提前佈局跡象）| 30% |

**Claude API 重點任務**：計算歷史上同類事件的平均反應幅度與方向，提供勝率統計。

**持有週期**：1–5 天（事件前後）
**風險提示**：事件結果不如預期時需立即停損

---

### 模式三：趨勢跟隨（Phase 1）

**策略說明**
順勢交易，跟隨強勢產業族群共振，買進創新高的領頭股，持有至趨勢反轉信號出現。

**因子篩選條件**
- 股價創 60 日新高
- 所屬產業熱力圖連續 3 日正向
- 連續 N 日收紅（N ≥ 3）
- 官股或外資持續買超

**AI 評分權重**

| 因子 | 權重 |
|------|------|
| 動能強度（創高幅度+速度）| 40% |
| 產業族群共振程度 | 30% |
| 籌碼集中度 | 30% |

**持有週期**：2–6 週
**停損邏輯**：跌破 10 日均線或產業族群轉弱

---

### 模式四：多/空策略（Phase 3）

**策略說明**
同時做多強勢股、做空弱勢股，透過抵銷市場系統性風險，在多空兩端賺取超額報酬。台股常見 130/30 配置（130% 多頭 + 30% 空頭）。

**台股限制**
- 融券需確認標的是否可借券
- 部分個股融券餘額不足
- 做空成本（借券費率）需納入計算

**配對邏輯範例**
```
多：台積電 2330（強勢，外資持續買）
空：聯電 2303（相對弱勢，籌碼鬆散）
目標：賺取兩者之間的相對價差
```

**實作條件**：Phase 2 元大 API 串接完成 + 借券功能確認後才啟動

---

### 模式五：市場中性策略（Phase 3）

**策略說明**
透過多空組合使整體投資組合 Beta 值接近 0，避免受大盤漲跌影響，只賺取選股的 Alpha。

**Beta 中性計算**
```
目標：Σ(多頭部位 × Beta) = Σ(空頭部位 × Beta)

範例：
多頭：台積電（Beta=1.12）× 100萬 = 112 Beta單位
空頭：需找 Beta 合計 = 112 的空頭組合
結果：組合 Beta ≈ 0，大盤漲跌對組合影響極小
```

**系統需求**：rolling_beta_60 欄位（已在規劃中）

---

### 模式六：配對對沖（Phase 3）

**策略說明**
找兩檔歷史相關性高的股票（同產業、同供應鏈），當兩者價差偏離歷史均值時，做多相對便宜的、做空相對昂貴的，等待均值回歸。

**高相關配對範例（台股）**

| 配對 | 說明 | 相關係數（參考）|
|------|------|------|
| 台積電 vs 聯電 | 同為晶圓代工 | ~0.75 |
| 台達電 vs 光寶科 | 同為電源供應 | ~0.72 |
| 富邦金 vs 國泰金 | 同為金控 | ~0.88 |

**系統需求**：macro_correlation 表擴充個股對個股相關係數計算

---

### 策略資料庫設計

```sql
-- 策略設定表
strategies (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(50),      -- 策略名稱
    mode          VARCHAR(30),      -- technical / event_driven / trend /
                                   -- long_short / market_neutral / pairs
    is_active     BOOLEAN DEFAULT TRUE,
    parameters    JSONB,            -- 各策略參數設定
    created_at    TIMESTAMP DEFAULT NOW()
)

-- 配對對沖設定表
pairs_config (
    id            SERIAL PRIMARY KEY,
    symbol_long   VARCHAR(10),      -- 做多標的
    symbol_short  VARCHAR(10),      -- 做空標的
    corr_60d      NUMERIC,          -- 60日相關係數
    spread_mean   NUMERIC,          -- 價差歷史均值
    spread_std    NUMERIC,          -- 價差標準差
    updated_at    TIMESTAMP
)
```


---

## 二十、UZI-Skill 整合模組

### 來源說明

參考開源專案 [wbh604/UZI-Skill](https://github.com/wbh604/UZI-Skill)，抽取三個核心邏輯整合進台股 AI 決策中心。原專案針對 A 股，本專案改寫為台股版本，資料來源全部替換為 FinMind + TWSE + 期交所。

---

### 整合項目一：台股版評審團（10位精簡版）

原專案有 51 位評審 × 180 條規則，我們精選 10 位最適合台股波段操作的評審，改寫量化規則：

#### 評審團組成

| 評審 | 風格 | 核心量化規則（台股版）|
|------|------|------|
| **巴菲特** | 價值投資 | ROE > 15% 連3年、負債比 < 40%、PE < 20 |
| **段永平** | 中長線價值 | 護城河評分 > 70、本業獲利率 > 10%、不碰投機股 |
| **達里奧** | 宏觀對沖 | 外資連買 > 5日、Beta < 1.2、匯率風險評估 |
| **索羅斯** | 反身性理論 | 市場共識偏離度 > 2σ、籌碼異動 > 均量3倍 |
| **利弗莫爾** | 技術趨勢 | 創60日新高、成交量放大 > 150%、趨勢線未破 |
| **米內爾維尼** | 超強勢股 | SEPA 條件：MA50>MA150>MA200、RS > 90 |
| **達瓦斯** | 箱型突破 | 突破前高箱型、帶量 > 均量2倍、停損箱底 |
| **西蒙斯** | 量化因子 | 動能因子 + 籌碼集中度 + 乖離率百分位 |
| **外資主力** | 台股法人 | 外資連買天數、官股護盤訊號、投信買超趨勢 |
| **台股游資** | 主力動向 | 券商分點集中度 > 60%、漲停鎖定、融券回補訊號 |

#### 評審團輸出格式

```
【台積電 2330 — 評審團投票】

✅ 看多（7票）：巴菲特 · 達里奧 · 利弗莫爾 · 米內爾維尼 · 達瓦斯 · 外資主力 · 台股游資
⚠️ 中性（2票）：西蒙斯 · 段永平
❌ 看空（1票）：索羅斯

【巴菲特】72分 · 中性偏多
  ✅ ROE 22.4%（連5年 > 15%）
  ✅ 負債比 28%（保守）
  ⚠️ PE 23倍（略高於20倍門檻）
  結論：護城河堅固，但估值稍貴，可持有不追高

【台股游資】91分 · 強烈看多
  ✅ 券商分點集中度 68%（主力鎖碼）
  ✅ 外資連買4日 +82億
  ✅ 官股護盤連3日
  結論：籌碼極度集中，主力意圖明顯，波段多方
```

#### 資料庫設計

```sql
-- 評審規則表
reviewer_rules (
    id            SERIAL PRIMARY KEY,
    reviewer_name VARCHAR(30),
    style         VARCHAR(20),    -- value/technical/macro/quant/local
    rules         JSONB,          -- 量化規則清單
    weight        NUMERIC         -- 在綜合評分中的權重
)

-- 評審結果表
reviewer_results (
    symbol        VARCHAR(10),
    date          DATE,
    reviewer_name VARCHAR(30),
    score         INT,            -- 0-100
    verdict       VARCHAR(10),   -- bullish/neutral/bearish
    triggered     JSONB,         -- 命中的規則清單
    summary       TEXT,          -- 評審評語
    PRIMARY KEY (symbol, date, reviewer_name)
)
```

---

### 整合項目二：三情景 IC 備忘錄

每日 AI 報告加入投資委員會（IC）備忘錄格式，Bull/Base/Bear 三情景目標價分析。

#### 輸出格式

```
【台積電 2330 — IC 投委會備忘錄】
分析日期：2026/06/04

━━ 情景分析 ━━

🟢 Bull（機率 35%）：目標價 1,250（+15.5%）
  核心假設：
  - 法說會上修 CoWoS 產能至 150K/月
  - 外資持續淨買，季度買超超過 300億
  - AI 伺服器需求維持強勁（NVDA 指引正面）
  觸發條件：法說會正面指引 + 外資連買 > 10日

⚪ Base（機率 45%）：目標價 1,100（+1.7%）
  核心假設：
  - 維持現有成長率，法說會符合預期
  - 外資中性，市場溫度計維持 60-80
  - 乖離率自然修正至 70 百分位

🔴 Bear（機率 20%）：目標價 950（-12.2%）
  核心假設：
  - 地緣政治升溫（台海緊張）
  - 美國出口管制進一步擴大
  - 外資大幅撤退，乖離率快速收斂

━━ 綜合建議 ━━
期望值目標價：(1250×0.35)+(1100×0.45)+(950×0.20) = 1,117
風險報酬比：Bull +15.5% / Bear -12.2% = 1.27（尚可）
建議操作：持有，停損設 MA20（964），停利分批至 1,150
```

#### 資料庫設計

```sql
-- IC 備忘錄表
ic_memo (
    symbol          VARCHAR(10),
    date            DATE,
    bull_price      NUMERIC,
    bull_prob       NUMERIC,
    bull_assumption TEXT,
    base_price      NUMERIC,
    base_prob       NUMERIC,
    base_assumption TEXT,
    bear_price      NUMERIC,
    bear_prob       NUMERIC,
    bear_assumption TEXT,
    expected_value  NUMERIC,    -- 期望值目標價
    risk_reward     NUMERIC,    -- 風險報酬比
    PRIMARY KEY (symbol, date)
)
```

---

### 整合項目三：多空辯論循環

當評審團中看多與看空票數接近時，觸發多空辯論循環，讓 Claude API 呈現雙方具體論據，幫助你做更好的決策。

#### 觸發條件
- 看多票數與看空票數差距 ≤ 3票
- 或 AI 綜合評分落在 45–65 分（模糊地帶）

#### 輸出格式

```
【多空大分歧 — 台積電 2330】

🔴 第一輪：索羅斯 看空
"乖離率89百分位，市場過度樂觀。
 反身性理論：當所有人都看多時，
 就是反轉的開始。目標下看 950。"
 引用規則：乖離率 > 85% × 市場溫度 > 75

🟢 利弗莫爾 反擊：
"你忽略了籌碼面。券商分點集中度68%，
 主力沒有出貨跡象。趨勢未破前不做空。
 創60日新高的股票，統計上有62%機率
 繼續上漲 10% 以上。"
 引用規則：分點集中度 > 60% × 創新高

🔴 第二輪：索羅斯 追擊：
"法說會倒數3天，事件風險被低估。
 歷史上法說會後平均震盪 ±4.8%，
 現在進場的時機點不對。"

🟢 外資主力 加入多方：
"外資已連買4日，不會在法說會前出貨。
 官股同步護盤，兩者同向代表機構對
 法說會有信心。這是提前佈局，不是風險。"

━━ 仲裁結論 ━━
多空分歧核心：法說會風險 vs 籌碼鎖定
建議：維持持有，但法說會前2天減碼至5成，
     聽完法說會結果再決定是否加回。
```

---

### 與現有系統的整合位置

| 整合項目 | 顯示位置 | 觸發時機 |
|------|------|------|
| 評審團投票 | 個股分析頁 → AI 決策中心下方展開 | 每日收盤後自動產生 |
| IC 三情景備忘錄 | 個股分析頁 → 獨立面板 | 每日收盤後自動產生 |
| 多空辯論循環 | AI 決策中心 → 「展開辯論」按鈕 | 評分 45–65 分時自動觸發 |

### Claude API Prompt 架構（整合版）

```python
system_prompt = """
你是台股 AI 決策中心，整合以下三個分析框架：

1. 評審團框架（10位）：
   依據各評審的量化規則，逐一評分並說明命中哪條規則。
   最後統計看多/中性/看空票數。

2. IC 備忘錄框架：
   給出 Bull/Base/Bear 三情景目標價，
   每個情景附上核心假設與觸發條件，
   計算期望值目標價與風險報酬比。

3. 多空辯論框架（評分 45-65 分時啟動）：
   讓看多與看空評審各發言2輪，
   每輪必須引用具體數字與規則，
   最後給出仲裁結論與操作建議。

所有輸出必須：
- 引用 JSON Context 中的具體數字
- 不得使用模糊語言（如「可能」「或許」）
- 操作建議必須包含具體價位（進場/停損/停利）
"""
```

### 開發排程

UZI-Skill 整合列為 **Sprint 4 的子任務**，在 Claude API 串接完成後加入：

```
Sprint 4 子任務：
  4-A：建立 reviewer_rules 資料表，寫入10位評審規則
  4-B：建立 reviewer_evaluator 函數（規則引擎）
  4-C：建立 ic_memo 產生函數（三情景計算）
  4-D：建立多空辯論觸發邏輯
  4-E：整合進 Claude API system prompt
  4-F：前端新增評審團投票 UI + IC 備忘錄面板
```


---

## 二十一、whale-quant 整合參考

### 來源說明

參考開源專案 [datawhalechina/whale-quant](https://github.com/datawhalechina/whale-quant)，這是一套完整的量化交易開源課程，8個章節全部以 Jupyter Notebook 實作，Star 數 2.4k。

定位與 UZI-Skill 互補：
- **whale-quant** = 量化工程底層（資料爬取、因子模型、回測框架）
- **UZI-Skill** = AI 決策層（評審團規則、三情景分析、多空辯論）

### 章節對應與用途

| 章節 | 內容 | 對應我們的模組 | 使用時機 |
|------|------|------|------|
| 第三章 | 股票數據獲取 | Data Agent 架構參考 | Sprint 2 |
| 第四章 | 量化選股策略 | 因子模型核心邏輯 | Sprint 3 |
| 第五章 | 量化擇時策略 | 進出場時機判斷 | Sprint 4 |
| 第六章 | 量化調倉策略 | 持倉管理模組 | Phase 2 |
| 第七章 | 量化回測 | Backtrader 回測框架 | Sprint 6 |
| 第八章 | 機器學習與量化策略 | 進階因子模型 | Phase 3 |

### 各章節整合說明

#### 第三章：股票數據獲取 → Sprint 2 直接參考

完整示範資料爬取、清洗、入庫流程。原版使用 akshare（A股），台股版替換資料源：

```python
# 原版 A 股
import akshare as ak
df = ak.stock_zh_a_hist(symbol="000001")

# 台股替換版
# TWSE 每日行情
import requests
url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
params = {"stockNo": "2330", "date": "20260601"}

# FinMind 籌碼資料
from FinMind.data import DataLoader
dl = DataLoader()
df = dl.taiwan_stock_institutional_investors(
    stock_id="2330",
    start_date="2026-01-01"
)
```

資料清洗邏輯與入庫架構直接參考第三章，只替換 API 來源。

#### 第四章：量化選股策略 → 因子模型核心

實作多因子選股完整邏輯，直接對應我們的 `factor_scan_daily` 表：

```python
# 因子計算範例（台股版）
def calculate_factors(df):
    # 動能因子：20日漲幅
    df['momentum_20'] = df['close'].pct_change(20)
    
    # 品質因子：ROE（需財報資料）
    df['quality'] = df['roe']
    
    # 技術因子：RSI 位階
    df['tech_score'] = calculate_rsi_score(df)
    
    # 籌碼因子：外資連買天數
    df['chip_score'] = df['foreign_consecutive_buy']
    
    # 標準化（Z-Score）
    for col in ['momentum_20', 'quality', 'tech_score', 'chip_score']:
        df[f'{col}_z'] = (df[col] - df[col].mean()) / df[col].std()
    
    # 加權合成
    df['factor_score'] = (
        df['momentum_20_z'] * 0.30 +
        df['quality_z']     * 0.20 +
        df['tech_score_z']  * 0.30 +
        df['chip_score_z']  * 0.20
    )
    return df
```

#### 第七章：量化回測 → Sprint 6 Backtrader 框架

完整 Backtrader 回測架構，含手續費、滑點、績效指標：

```python
import backtrader as bt

class TaiwanStockStrategy(bt.Strategy):
    def __init__(self):
        self.macd = bt.indicators.MACD(self.data)
        self.rsi = bt.indicators.RSI(self.data)
    
    def next(self):
        # 進場條件：MACD 黃金交叉 + RSI < 70
        if self.macd.macd[0] > self.macd.signal[0] and self.rsi[0] < 70:
            self.buy()
        # 出場條件：跌破 MA20
        elif self.data.close[0] < self.sma20[0]:
            self.sell()

# 回測設定
cerebro = bt.Cerebro()
cerebro.addstrategy(TaiwanStockStrategy)
cerebro.broker.setcommission(commission=0.001425)  # 台股手續費
cerebro.broker.set_slippage_perc(0.001)            # 滑點
cerebro.run()
```

輸出績效指標：總報酬率、夏普比率、最大回撤、勝率、平均持有天數。

### Hermes Sprint 任務指令補充

在各 Sprint 的 Hermes 任務指令中，附上對應章節連結讓 Hermes 讀取參考：

```
Sprint 2 Data Agent 任務：
  參考文件：
  https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch03/ch03.ipynb

Sprint 3 因子模型任務：
  參考文件：
  https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch04/ch04.ipynb

Sprint 6 回測模組任務：
  參考文件：
  https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch07/ch07.ipynb
```

### 與 UZI-Skill 的完整分工

```
資料層（whale-quant 第三章）
  ↓
因子模型層（whale-quant 第四章）
  ↓
擇時策略層（whale-quant 第五章）
  ↓
AI 決策層（UZI-Skill 評審團 + IC備忘錄 + 多空辯論）
  ↓
回測驗證層（whale-quant 第七章）
  ↓
執行層（元大 API + Hermes Agent）
```


---

## 二十二、TradingView Webhook 串接

### 前提條件
需升級 TradingView **Plus 方案以上**（$24.95/月）才能使用 Webhook Alert 功能。
Phase 1 先用 AI 替代指標信號，升級後無縫切換至本章架構。

### 整體流程

```
TradingView Pine Script 觸發條件
    ↓ Alert 觸發
TradingView Webhook POST
    ↓ HTTPS
FastAPI /api/webhook/tradingview
    ↓ 解析信號
Redis 信號佇列
    ↓ 推播
前端 WebSocket 即時顯示
    ↓ 選擇性
Claude Code Agent 決策 → 元大 API 下單
```

### Pine Script 信號格式設計

在 TradingView 建立 Alert 時，Message 欄位填入以下 JSON：

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": {{close}},
  "volume": {{volume}},
  "indicator": "MACD_CROSS",
  "timeframe": "{{interval}}",
  "timestamp": "{{time}}"
}
```

常用觸發條件範例：

```pine
// MACD 黃金交叉
[macdLine, signalLine, _] = ta.macd(close, 12, 26, 9)
if ta.crossover(macdLine, signalLine)
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"MACD_CROSS","price":' + str.tostring(close) + '}', alert.freq_once_per_bar)

// RSI 超賣反彈
rsi = ta.rsi(close, 14)
if ta.crossover(rsi, 30)
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"RSI_OVERSOLD","price":' + str.tostring(close) + '}', alert.freq_once_per_bar)

// 突破 20MA 帶量
sma20 = ta.sma(close, 20)
vol_avg = ta.sma(volume, 5)
if close > sma20 and volume > vol_avg * 1.5
    alert('{"symbol":"{{ticker}}","action":"BUY","indicator":"MA20_BREAKOUT","price":' + str.tostring(close) + '}', alert.freq_once_per_bar)
```

### FastAPI Webhook 端點

```python
# backend/routers/webhook.py
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import redis
import json
import hmac
import hashlib

router = APIRouter()

class TVSignal(BaseModel):
    symbol: str
    action: str          # BUY / SELL / CLOSE
    price: float
    indicator: str       # MACD_CROSS / RSI_OVERSOLD / MA20_BREAKOUT
    timeframe: str
    timestamp: str

WEBHOOK_SECRET = os.getenv("TV_WEBHOOK_SECRET")

@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    # 驗證來源（防偽造）
    body = await request.body()
    signature = request.headers.get("X-TV-Signature", "")
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    signal = TVSignal(**json.loads(body))

    # 台股代號轉換（TradingView 格式 → 台股代號）
    # TW:2330 → 2330
    symbol = signal.symbol.replace("TWSE:", "").replace("TW:", "")

    # 寫入 Redis 信號佇列
    redis_client.lpush("tv_signals", json.dumps({
        "symbol": symbol,
        "action": signal.action,
        "price": signal.price,
        "indicator": signal.indicator,
        "timeframe": signal.timeframe,
        "timestamp": signal.timestamp,
        "source": "tradingview"
    }))

    # WebSocket 推播到前端
    await websocket_manager.broadcast({
        "type": "tv_signal",
        "data": signal.dict()
    })

    return {"status": "received", "symbol": symbol}
```

### 信號資料庫設計

```sql
-- TradingView 信號記錄表
tv_signals (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10),
    action      VARCHAR(10),     -- BUY / SELL / CLOSE
    price       NUMERIC,
    indicator   VARCHAR(50),     -- 觸發的指標名稱
    timeframe   VARCHAR(10),     -- 1D / 4H / 1H
    source      VARCHAR(20),     -- tradingview / ai_substitute
    triggered_at TIMESTAMP,
    processed   BOOLEAN DEFAULT FALSE,
    order_id    VARCHAR(50)      -- 若已下單，記錄訂單ID
)
```

### 前端信號顯示（TradingView 信號模組）

收到 Webhook 後，前端即時顯示：

```
【即時信號】14:32:15
📡 TradingView → 台積電 2330
指標：MACD 黃金交叉（日線）
動作：買進
價格：1,082
[確認下單] [忽略]
```

### AI 替代模式（Phase 1，升級前）

尚未升級 TradingView Plus 時，由後端 pandas-ta 計算相同指標，模擬信號輸出：

```python
# backend/agents/signal_simulator.py
import pandas_ta as ta

def simulate_tv_signals(symbol: str, df: pd.DataFrame) -> list:
    signals = []

    # MACD 黃金交叉
    macd = ta.macd(df['close'])
    if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1] and \
       macd['MACD_12_26_9'].iloc[-2] <= macd['MACDs_12_26_9'].iloc[-2]:
        signals.append({
            "symbol": symbol,
            "action": "BUY",
            "indicator": "MACD_CROSS",
            "source": "ai_substitute"
        })

    # RSI 超賣
    rsi = ta.rsi(df['close'], length=14)
    if rsi.iloc[-1] > 30 and rsi.iloc[-2] <= 30:
        signals.append({
            "symbol": symbol,
            "action": "BUY",
            "indicator": "RSI_OVERSOLD",
            "source": "ai_substitute"
        })

    return signals
```

---

## 二十三、元大證券 API 自動下單

### 申請流程（需本人辦理）

```
Step 1：開立元大證券帳戶（已有帳戶可跳過）
Step 2：申請「元大證券 API」開發者資格
         → 前往元大證券官網 → 數位服務 → API 交易
Step 3：下載並安裝元大 API SDK（Windows 版）
Step 4：取得憑證與 API 金鑰
Step 5：在 WSL2 環境設定憑證路徑
Step 6：模擬帳戶測試（至少 1 個月）→ 才進入真實帳戶
```

### API 功能清單

| 功能 | API 方法 | 說明 |
|------|------|------|
| 查詢帳戶餘額 | `get_account_balance()` | 可用資金、總資產 |
| 查詢持倉 | `get_positions()` | 持股清單、損益 |
| 查詢即時報價 | `get_quote(symbol)` | 現價、五檔掛單 |
| 市價買進 | `place_order(type='market', side='buy')` | 立即成交 |
| 限價買進 | `place_order(type='limit', price=X)` | 指定價格掛單 |
| 市價賣出 | `place_order(type='market', side='sell')` | 立即成交 |
| 停損單 | `place_order(type='stop', stop_price=X)` | 觸價後市價賣出 |
| 取消委託 | `cancel_order(order_id)` | 取消未成交委託 |
| 查詢委託 | `get_orders()` | 今日委託清單 |

### Claude Code Agent Tool Use 架構

Claude Code 作為決策 Agent，透過 Tool Use 呼叫元大 API：

```python
# backend/agents/trading_agent.py
import anthropic

client = anthropic.Anthropic()

# 定義工具清單
tools = [
    {
        "name": "get_quote",
        "description": "查詢台股即時報價",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代號，如 2330"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_position",
        "description": "查詢目前持倉與損益",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代號"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "check_risk",
        "description": "執行風控審查，確認是否符合下單條件",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "action": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "integer"},
                "price": {"type": "number"}
            },
            "required": ["symbol", "action", "quantity", "price"]
        }
    },
    {
        "name": "place_order",
        "description": "呼叫元大 API 執行下單",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "action": {"type": "string", "enum": ["buy", "sell"]},
                "order_type": {"type": "string", "enum": ["market", "limit", "stop"]},
                "quantity": {"type": "integer", "description": "張數"},
                "price": {"type": "number", "description": "限價或停損價"},
            },
            "required": ["symbol", "action", "order_type", "quantity"]
        }
    },
    {
        "name": "send_notify",
        "description": "發送 Telegram 通知",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        }
    }
]

def run_trading_agent(signal: dict, ai_context: dict):
    """
    接收 TradingView 信號 + AI 分析結果，決定是否下單
    """
    messages = [{
        "role": "user",
        "content": f"""
        收到交易信號，請依序執行：
        1. 查詢 {signal['symbol']} 即時報價
        2. 查詢目前持倉
        3. 執行風控審查
        4. 若風控通過，執行下單
        5. 發送 Telegram 通知結果

        信號資訊：{signal}
        AI 分析：{ai_context}

        風控規則：
        - 單筆損失上限：總資產 2%
        - 停損設定：買入價 × (1 - 2.5 × ATR/price)
        - 同一檔股票最多持有總資產 10%
        - 若 AI 評分 < 70 分，不執行自動下單
        """
    }]

    # Agent 循環執行 Tool Use
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return response
```

### 風控保護機制（六層）

```python
# backend/risk/risk_manager.py

class RiskManager:

    def check_all(self, symbol, action, quantity, price, account):
        checks = [
            self.check_max_loss_per_trade(quantity, price, account),
            self.check_position_limit(symbol, quantity, price, account),
            self.check_daily_loss_limit(account),
            self.check_ai_score(symbol),
            self.check_market_hours(),
            self.check_settlement_risk(symbol)
        ]
        return all(checks)

    def check_max_loss_per_trade(self, quantity, price, account):
        """單筆損失不超過總資產 2%"""
        max_loss = account['total_assets'] * 0.02
        atr = get_atr(symbol)
        estimated_loss = quantity * 1000 * atr * 2.5
        return estimated_loss <= max_loss

    def check_position_limit(self, symbol, quantity, price, account):
        """單一股票不超過總資產 10%"""
        position_value = quantity * 1000 * price
        return position_value <= account['total_assets'] * 0.10

    def check_daily_loss_limit(self, account):
        """當日虧損不超過總資產 5%"""
        return account['daily_pnl'] >= -(account['total_assets'] * 0.05)

    def check_ai_score(self, symbol):
        """AI 評分必須 >= 70 才允許自動下單"""
        score = get_latest_ai_score(symbol)
        return score >= 70

    def check_market_hours():
        """只在交易時間內下單（09:00-13:30）"""
        now = datetime.now(tz=taiwan_tz)
        return time(9, 0) <= now.time() <= time(13, 30)

    def check_settlement_risk(self, symbol):
        """台指期結算日前 2 天，禁止自動下單"""
        days_to_settlement = get_days_to_settlement()
        return days_to_settlement > 2
```

### 下單記錄資料庫

```sql
-- 委託記錄表
orders (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(10),
    action          VARCHAR(10),      -- buy / sell
    order_type      VARCHAR(10),      -- market / limit / stop
    quantity        INT,              -- 張數
    price           NUMERIC,          -- 委託價
    filled_price    NUMERIC,          -- 成交價
    filled_qty      INT,              -- 成交張數
    status          VARCHAR(20),      -- pending / filled / cancelled / rejected
    signal_source   VARCHAR(20),      -- tradingview / ai_auto / manual
    ai_score        INT,              -- 下單當時 AI 評分
    risk_checked    BOOLEAN,          -- 風控是否通過
    yuanta_order_id VARCHAR(50),      -- 元大 API 回傳的委託編號
    stop_loss_price NUMERIC,          -- 停損價
    take_profit_price NUMERIC,        -- 停利價
    created_at      TIMESTAMP DEFAULT NOW(),
    filled_at       TIMESTAMP
)

-- 帳戶快照表（每日收盤後記錄）
account_snapshots (
    date            DATE PRIMARY KEY,
    total_assets    NUMERIC,          -- 總資產
    cash            NUMERIC,          -- 現金
    position_value  NUMERIC,          -- 持股市值
    daily_pnl       NUMERIC,          -- 當日損益
    total_pnl       NUMERIC,          -- 累計損益
    win_rate        NUMERIC           -- 勝率
)
```

### 手動 / 自動模式切換

系統設計三種模式，可在設定頁隨時切換：

```
模式一：純看盤（Phase 1）
  → 只顯示 AI 建議，不連接元大 API

模式二：半自動（Phase 2）
  → AI 發出信號 → Telegram 推播
  → 你手機確認 → 才執行下單

模式三：全自動（Phase 3）
  → AI 評分 ≥ 70 + 風控全過 → 自動下單
  → 異常才介入
```

```sql
-- 系統設定表
system_config (
    key     VARCHAR(50) PRIMARY KEY,
    value   TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
)

-- 預設設定
INSERT INTO system_config VALUES
  ('trading_mode', 'manual', NOW()),       -- manual / semi_auto / full_auto
  ('auto_order_min_score', '70', NOW()),   -- 自動下單最低 AI 分數
  ('max_position_pct', '10', NOW()),       -- 單一持股上限 %
  ('daily_loss_limit_pct', '5', NOW()),    -- 當日虧損上限 %
  ('tv_webhook_enabled', 'false', NOW());  -- TradingView Webhook 開關
```

### 模擬帳戶測試計畫

**Phase 2 進入真實帳戶前，必須完成以下測試：**

```
Week 1-2：模擬帳戶，手動觸發下單，確認 API 連線正常
Week 3-4：模擬帳戶，半自動模式，確認風控邏輯正確
Week 5-6：模擬帳戶，全自動模式，觀察 Agent 決策品質
Week 7-8：小額真實帳戶測試（每筆不超過 NT$10,000）
Week 9+：確認勝率 > 55% 且最大回撤 < 10% 後，才擴大資金
```


---

## 二十二、多 Agent 決策架構

### 設計理念

目標不是把勝率硬拉到 80%（這在量化交易界是危險信號），而是透過多個專業 Agent 各司其職，**提升決策品質、減少漏看風險**，實現以下合理目標：

```
勝率：55-65%（超過 65% 要高度懷疑過擬合）
賺賠比：2:1 以上（賺的時候比虧的時候多）
最大回撤：-12% 以內
夏普比率：1.5 以上
年化報酬：穩定跑贏 0050
```

> 西蒙斯大獎章基金勝率約 50-55%，靠的是極小優勢的持續累積，而非高勝率。

---

### 六個專業 Agent 分工

```
全市場 1,800+ 檔
      ↓
[Agent 1：選股 Agent]
  全市場掃描，輸出候選清單 20-30 檔
      ↓
[Agent 2：技術分析 Agent]    [Agent 3：籌碼 Agent]
  技術指標評分 + 點位          主力意圖 + 法人動向
      ↓                            ↓
[Agent 4：風險 Agent]
  事件風險 + 乖離率 + 倉位建議
      ↓
[Agent 5：魔鬼代言人 Agent]
  專門找反駁理由，強迫思考看空論據
      ↓
[Agent 6：仲裁 Agent]
  整合所有輸出，給最終評分與操作建議
      ↓
你做最終決策
```

---

### Agent 1：選股 Agent（Factor Scanner）

**職責**：只做篩選，不做判斷，輸出候選清單

```python
# agents/factor_scanner.py
SYSTEM_PROMPT_SCANNER = """
你是選股篩選器，職責是從全市場找出符合條件的候選股。
你只做客觀篩選，不給買賣建議。
輸出格式：JSON 清單，包含股票代號、各因子狀態、綜合分數。

篩選條件（全部通過才進入候選）：
1. 日均成交額 > 3億（流動性）
2. 股價 > MA60（多頭趨勢）
3. 20日漲幅 > 0%（動能正向）
4. 外資近5日淨買超（法人認同）
5. ATR/股價 < 8%（波動可控）
6. 融資增幅 < 20%（籌碼健康）

評分因子（Z-Score 標準化後加權）：
- 動能因子（20日漲幅）：30%
- 技術因子（RSI/MACD/KD綜合）：30%
- 籌碼因子（外資連買天數）：20%
- 品質因子（乖離率百分位反向）：20%

輸出前30名，依綜合分數排序。
"""
```

---

### Agent 2：技術分析 Agent

**職責**：深度技術指標分析，給出進出場點位

```python
SYSTEM_PROMPT_TECHNICAL = """
你是專業技術分析師，只分析技術面，不考慮籌碼與基本面。
你的輸出必須包含：

1. 趨勢判斷：多頭 / 盤整 / 空頭
2. 關鍵支撐壓力：最近3個重要價位
3. 技術指標狀態：
   - RSI：數值 + 超買/超賣/中性
   - MACD：黃金交叉/死亡交叉/待確認
   - KD：K>D/K<D + 數值
   - 布林通道：上軌/中軌/下軌 + 現價位置
   - VWAP：價格在 VWAP 上方/下方
4. 進場建議：
   - 理想進場價（回測至支撐）
   - 次優進場價（現價附近）
5. 出場建議：
   - 停損價（跌破哪個支撐）
   - 停利目標（前高或壓力位）
6. 技術評分：0-100

你只做技術分析，不評論籌碼或事件風險。
"""
```

---

### Agent 3：籌碼分析 Agent

**職責**：解讀主力意圖，判斷法人動向

```python
SYSTEM_PROMPT_CHIP = """
你是籌碼分析師，專精解讀主力行為與法人動向。
你的輸出必須包含：

1. 外資判斷：
   - 連續買超/賣超天數
   - 近5日合計金額
   - 趨勢判斷（加碼/減碼/觀望）

2. 官股判斷：
   - 是否有護盤跡象
   - 連續介入天數
   - 撐盤 / 出貨 / 觀望

3. 券商分點：
   - 集中度%（前10大買超占成交量）
   - 是否有特定主力鎖碼
   - Top3 買超分點名稱

4. 大戶集保：
   - 400張以上持股比例趨勢（增加/減少）
   - 主力是否在默默增持

5. 融資融券：
   - 融資增減趨勢（危險/正常/健康）
   - 融券回補壓力

6. 籌碼評分：0-100
7. 主力意圖：鎖碼吸籌 / 出貨分散 / 無明顯意圖

你只分析籌碼，不評論技術面。
"""
```

---

### Agent 4：風險評估 Agent

**職責**：量化各種風險，給出倉位建議

```python
SYSTEM_PROMPT_RISK = """
你是風險管理師，職責是找出所有可能讓這筆交易失敗的風險。
你傾向保守，寧願錯過機會也不願承擔不必要風險。

你的輸出必須包含：

1. 事件風險（高/中/低）：
   - 法說會倒數天數 + 歷史平均震盪幅度
   - 月營收公布倒數天數
   - 台指期結算倒數天數
   - FOMC 倒數天數

2. 估值風險：
   - 20MA 乖離率歷史百分位
   - 過熱判斷（>85% = 高風險）

3. 波動風險：
   - ATR(14) 絕對值
   - 滾動 Beta（市場連動性）

4. 宏觀風險：
   - 與費半相關係數（美股科技拖累風險）
   - 美元強弱影響

5. 倉位建議：
   - 建議持倉比例（佔總資產%）
   - 最大虧損容忍（ATR × 2.5 = 停損距離）

6. 風險評分：0-100（分數越高 = 風險越高）
7. 綜合風險等級：低 / 中 / 高 / 極高

你只評估風險，不做買賣建議。
"""
```

---

### Agent 5：魔鬼代言人 Agent（Devil's Advocate）

**職責**：專門找看空理由，強迫你思考反面論據

```python
SYSTEM_PROMPT_DEVIL = """
你是魔鬼代言人，你的唯一職責是找出「為什麼不該買這檔股票」的理由。
不管其他分析師多看好，你都要找出反駁。

你必須從以下角度提出質疑：

1. 技術面弱點：
   - 有哪些技術指標其實是反轉訊號？
   - 成交量是否有疑慮？

2. 籌碼面疑慮：
   - 外資買超是否只是避險對沖？
   - 券商分點集中是否是出貨假象？

3. 事件面地雷：
   - 即將到來的事件有哪些可能讓股價下跌？
   - 歷史上類似情境最壞的結果是什麼？

4. 估值面風險：
   - 現在進場是追高嗎？
   - 如果大盤回檔，這檔會跌多深？

5. 宏觀面威脅：
   - 美股若下跌，這檔的 Beta 代表什麼？
   - 有哪些外部風險被市場低估？

你的輸出格式：
- 列出 3-5 個最強的看空理由
- 每個理由附上具體數字支撐
- 最後給「看空強度」：弱 / 中 / 強 / 極強

記住：你不需要客觀，你的職責就是唱反調。
"""
```

---

### Agent 6：仲裁 Agent（Final Arbiter）

**職責**：整合所有 Agent 輸出，給出最終決策

```python
SYSTEM_PROMPT_ARBITER = """
你是投資委員會主席，你收到了以下五位分析師的報告：
- 選股 Agent：因子評分
- 技術分析 Agent：技術評分 + 點位
- 籌碼 Agent：籌碼評分 + 主力意圖
- 風險 Agent：風險評分 + 倉位建議
- 魔鬼代言人：看空理由清單

你的職責是綜合所有意見，給出最終裁決。

加權規則：
- 技術評分：25%
- 籌碼評分：30%
- 風險評分（反向）：25%
- 魔鬼代言人強度（反向）：20%

最終輸出必須包含：
1. 綜合評分（0-100）
2. 操作建議：強力買進 / 買進 / 持有 / 觀望 / 減碼 / 賣出
3. 理想進場價 / 停損價 / 停利目標
4. 建議持倉比例
5. 最關鍵的3個正面因素
6. 最關鍵的3個風險因素
7. 一句話結論（30字以內）

你不做模糊表達，你的每個建議都要有具體價位。
"""
```

---

### 執行流程

```python
# agents/multi_agent_engine.py

async def run_multi_agent_analysis(symbol: str) -> dict:
    """
    六個 Agent 依序執行，後面的 Agent 可以看到前面的結果
    總共約 6 次 Claude API 呼叫，結果快取至 Redis
    """
    context = build_ai_context(symbol)

    # Agent 1：選股（批次跑，不在這裡執行）
    # Agent 2：技術分析
    technical_result = await call_agent(
        "technical", SYSTEM_PROMPT_TECHNICAL, context
    )

    # Agent 3：籌碼分析
    chip_result = await call_agent(
        "chip", SYSTEM_PROMPT_CHIP, context
    )

    # Agent 4：風險評估
    risk_result = await call_agent(
        "risk", SYSTEM_PROMPT_RISK, context
    )

    # Agent 5：魔鬼代言人（看到前三個結果）
    devil_context = {
        **context,
        "technical_analysis": technical_result,
        "chip_analysis": chip_result,
        "risk_assessment": risk_result
    }
    devil_result = await call_agent(
        "devil", SYSTEM_PROMPT_DEVIL, devil_context
    )

    # Agent 6：仲裁（看到所有結果）
    final_context = {
        **devil_context,
        "devil_advocate": devil_result
    }
    final_result = await call_agent(
        "arbiter", SYSTEM_PROMPT_ARBITER, final_context
    )

    # 整合結果
    return {
        "symbol": symbol,
        "technical": technical_result,
        "chip": chip_result,
        "risk": risk_result,
        "devil": devil_result,
        "final": final_result,
        "generated_at": datetime.now().isoformat()
    }
```

---

### Token 費用估算（多 Agent 版）

```
每次分析 = 6 個 Agent 呼叫
每個 Agent 平均：input 2,000 + output 600 = 2,600 token
單次分析：6 × 2,600 = 15,600 token

自選股 10 檔 × 每日 1 次 = 156,000 token/日
月費估算：約 NT$350-450/月

Redis 快取策略（同前）：
每日收盤後跑一次，結果快取到隔日 09:00
用戶查詢時直接回傳快取，不重複呼叫
```

---

### 真實可期待的績效目標

```
Phase 1 回測目標：
  勝率：55-62%
  賺賠比：1.8-2.2
  最大回撤：< -12%
  夏普比率：> 1.2
  年化報酬：跑贏 0050 5-10 個百分點

Phase 2 實盤驗證：
  實盤與回測差距 < 10%
  連續 3 個月正報酬

Phase 3 長期目標：
  年化報酬穩定 15-25%
  最大回撤控制 < -15%
```

> **重要提醒**：勝率超過 65% 要高度懷疑過擬合。賺賠比 2:1 + 勝率 58% 的系統，長期複利遠勝勝率 80% 但賺賠比 0.8:1 的系統。

---

### 新增資料表

```sql
-- 各 Agent 分析結果
agent_results (
    id            SERIAL PRIMARY KEY,
    symbol        VARCHAR(10),
    date          DATE,
    agent_type    VARCHAR(20),  -- technical/chip/risk/devil/arbiter
    score         INT,
    output        JSONB,        -- 完整輸出
    tokens_used   INT,
    created_at    TIMESTAMP DEFAULT NOW()
)
```

### 開發排程

多 Agent 架構列為 **Sprint 4 子任務 4-G**，在單一 Claude API 串接穩定後加入：

```
4-G-1：建立各 Agent 的 System Prompt
4-G-2：建立 multi_agent_engine.py 執行框架
4-G-3：建立 agent_results 資料表
4-G-4：前端新增各 Agent 結果展開面板
4-G-5：整合進每日自動分析排程
```

