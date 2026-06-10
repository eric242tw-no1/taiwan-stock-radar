# Taiwan AI Stock Radar — 04 AI 決策引擎
> Sprint 4 AI 串接時使用

## 架構總覽

```
stock_indicators_daily（技術指標）
large_holders_weekly（大戶集保）
macro_correlation（宏觀連動）
chip_data（三大法人）
branch_chip_daily（券商分點）
calendar_events（行事曆）
        ↓
build_ai_context() → 結構化 JSON
        ↓
Claude API（claude-sonnet-4）
        ↓
評審團投票 + IC備忘錄 + 多空辯論
        ↓
Redis 快取（每日一次，TTL 到隔日09:00）
        ↓
daily_ai_report 表持久化
```

---

## System Prompt（完整版）

```python
SYSTEM_PROMPT = """
你是台股 AI 決策中心，整合三個分析框架，所有輸出必須：
1. 引用 JSON Context 中的具體數字
2. 不使用模糊語言（如「可能」「或許」）
3. 操作建議必須包含具體價位

===== 框架一：評審團（10位台股版）=====

依據以下評審的量化規則，逐一評分並說明命中哪條規則：

【巴菲特】價值投資
  ✅ ROE > 15%（連3年） ✅ 負債比 < 40% ✅ PE < 20

【段永平】中長線價值
  ✅ 本業獲利率 > 10% ✅ 護城河明確 ❌ 避免高本益比投機

【達里奧】宏觀對沖
  ✅ 外資連買 > 5日 ✅ Beta < 1.2 ✅ 匯率風險低

【索羅斯】反身性
  ✅ 市場共識偏離 > 2σ ✅ 籌碼異動 > 均量3倍

【利弗莫爾】技術趨勢
  ✅ 創60日新高 ✅ 成交量 > 均量150% ✅ 趨勢線未破

【米內爾維尼】超強勢股 SEPA
  ✅ 股價 > MA50 > MA150 > MA200 ✅ RS > 90

【達瓦斯】箱型突破
  ✅ 突破前高箱型 ✅ 帶量 > 均量2倍 ✅ 停損箱底

【西蒙斯】量化因子
  ✅ 動能因子正 ✅ 籌碼集中度 > 60% ✅ 乖離率百分位 < 80%

【外資主力】台股法人
  ✅ 外資連買天數 ✅ 官股護盤訊號 ✅ 投信買超趨勢

【台股游資】主力動向
  ✅ 券商分點集中度 > 60% ✅ 漲停鎖定 ✅ 融券回補訊號

輸出格式：
{評審名} {分數}分 · {看多/中性/看空}
  ✅ {命中規則1}
  ⚠️ {接近但未達標規則}
  ❌ {未達標規則}
  結論：{一句話評語}

最後統計：看多X票 / 中性Y票 / 看空Z票

===== 框架二：IC 投委會備忘錄 =====

給出三情景目標價：
🟢 Bull（機率%）：目標價 → 核心假設 + 觸發條件
⚪ Base（機率%）：目標價 → 核心假設
🔴 Bear（機率%）：目標價 → 核心假設

期望值 = Bull × prob + Base × prob + Bear × prob
風險報酬比 = Bull上漲幅度 / Bear下跌幅度

===== 框架三：多空辯論（評分45-65分時啟動）=====

看多評審 vs 看空評審，各發言2輪
每輪必須引用具體數字
最後仲裁結論 + 操作建議含具體價位

===== 最終輸出必含 =====
- AI 綜合評分（0-100）
- 操作建議（買進/持有/觀望/減倉/賣出）
- 理想買入價 / 次優買入價
- 止損價（參考 ATR × 2.5）
- 止盈目標
- 風險提示（事件行事曆相關）
"""
```

---

## Context JSON 結構

```python
def build_ai_context(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": get_stock_name(symbol),

        "price_data": {
            "close": ...,
            "ma20_bias": ...,        # 乖離率%
            "bias_percentile": ...,  # 歷史百分位
            "is_overheat": ...
        },

        "technicals": {
            "rsi_14": ...,
            "macd_signal": ...,      # bullish/bearish/neutral
            "kd_k": ...,
            "kd_d": ...,
            "ma_arrangement": ...    # bullish/bearish
        },

        "risk_metrics": {
            "atr_14": ...,           # 絕對波動幅度
            "rolling_beta_60": ...,  # 與大盤連動性
            "stop_loss_ref": ...     # close - 2.5*ATR
        },

        "chip_data": {
            "foreign_buy": ...,
            "foreign_consecutive_days": ...,
            "investment_buy": ...,
            "dealer_buy": ...,
            "margin_trend": ...,
            "short_trend": ...
        },

        "branch_data": {
            "concentration_5d": ..., # 前10大分點5日集中度%
            "top5_buyers": [...],
            "top5_sellers": [...]
        },

        "large_holders": {
            "pct_over_400": ...,     # 400張以上持股比例
            "pct_over_1000": ...,
            "trend": ...             # increasing/decreasing/stable
        },

        "macro_correlation": {
            "corr_sox": ...,         # 與費半相關係數
            "corr_dxy": ...,         # 與美元指數相關係數
            "sox_yesterday": ...     # 費半昨日漲跌%
        },

        "calendar_events": {
            "earnings_call_days": ...,      # 法說會倒數
            "monthly_revenue_days": ...,    # 月營收倒數
            "ex_dividend_days": ...,        # 除息倒數
            "futures_settlement_days": ..., # 期指結算倒數
            "fomc_days": ...                # FOMC倒數
        },

        "gov_stock": {
            "total_buy_today": ...,
            "consecutive_days": ...,
            "signal": ...            # 撐盤介入/觀望/出貨
        },

        "market_context": {
            "market_temperature": ...,  # 市場溫度 0-100
            "advancing_stocks": ...,
            "declining_stocks": ...,
            "limit_up_count": ...
        }
    }
```

---

## Redis 快取策略

```python
import redis
from datetime import datetime, time
import pytz

taiwan_tz = pytz.timezone('Asia/Taipei')
redis_client = redis.Redis()

def get_cache_ttl() -> int:
    """計算到隔日 09:00 的秒數"""
    now = datetime.now(taiwan_tz)
    tomorrow_9am = now.replace(hour=9, minute=0, second=0) + timedelta(days=1)
    return int((tomorrow_9am - now).total_seconds())

def get_ai_analysis(symbol: str) -> dict:
    today = datetime.now(taiwan_tz).strftime("%Y%m%d")
    cache_key = f"ai_report:{symbol}:{today}"

    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)  # 直接回傳，不呼叫 API

    context = build_ai_context(symbol)
    result = call_claude_api(symbol, context)

    ttl = get_cache_ttl()
    redis_client.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ttl)
    save_daily_ai_report(symbol, result)

    return result
```

---

## 前端 AI 決策中心 UI 組件

```
┌─────────────────────────────┐
│ AI 決策中心  [Claude API]   │
│                             │
│         ⭕ 87              │
│        買進分數             │
│                             │
│    波段多方 — 持有           │
│                             │
│ ▲ MACD 黃金交叉（日線）     │
│ ▲ 外資連買 4 日 +82億       │
│ ▲ 官股連買 3 日（撐盤）     │
│ ▲ 分點集中度 68%            │
│ ! 乖離率 89 百分位（偏高）  │
│ ! 法說會倒數 3 天           │
│ ⚠️ 結算倒數 18 天           │
│                             │
│ 止損：964（MA20）           │
│ 止盈：1,150（前高）         │
│                             │
│ [展開評審團] [展開IC備忘錄] │
│ [深度分析 ↗]               │
└─────────────────────────────┘
```

---

## Token 費用估算

```
波段操作每日 50 次查詢：
  - 有 Redis 快取：每股每日只呼叫 1 次
  - 自選股 10 檔 × 1次 = 10 次呼叫
  - 每次 input ~2,000 token + output ~800 token
  - 費用：10 × 2,800 token = 28,000 token/日
  - 月費：約 NT$80-120（遠低於無快取的 NT$240）
```

---

## 多 Agent 架構（Sprint 4-G）

### 六個 Agent 分工

```
選股 Agent → 技術 Agent → 籌碼 Agent → 風險 Agent
                                            ↓
                              魔鬼代言人 Agent（找反駁）
                                            ↓
                                    仲裁 Agent（最終裁決）
```

### 績效目標（務實版）

```
勝率：55-62%（超過 65% = 懷疑過擬合）
賺賠比：1.8-2.2
最大回撤：< -12%
夏普比率：> 1.2
```

### 各 Agent System Prompt 重點

**技術 Agent**：只看技術面，輸出趨勢判斷 + 支撐壓力 + 技術評分 0-100

**籌碼 Agent**：只看籌碼，輸出外資/官股/分點集中度 + 主力意圖 + 籌碼評分 0-100

**風險 Agent**：只評估風險，輸出事件風險 + 乖離率過熱 + 倉位建議 + 風險評分 0-100

**魔鬼代言人**：專門找看空理由，列出 3-5 個反駁論點 + 看空強度（弱/中/強/極強）

**仲裁 Agent**：整合所有報告，加權計算最終評分，輸出具體進場/停損/停利價位

### Token 估算

```
每次分析 = 6 Agent × 2,600 token = 15,600 token
10 檔自選股 × 每日 1 次 = 156,000 token/日
月費：約 NT$350-450（Redis 快取後）
```

### 新增資料表

```sql
agent_results (
    id         SERIAL PRIMARY KEY,
    symbol     VARCHAR(10),
    date       DATE,
    agent_type VARCHAR(20),  -- technical/chip/risk/devil/arbiter
    score      INT,
    output     JSONB,
    tokens_used INT,
    created_at TIMESTAMP DEFAULT NOW()
)
```
