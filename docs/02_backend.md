# Taiwan AI Stock Radar — 02 後端與 Data Agent
> Sprint 2 使用，參考 whale-quant 第三章

## 專案目錄結構

```
backend/
├── main.py
├── requirements.txt
├── Dockerfile
├── schema.sql
├── routers/
│   ├── stock.py        # /api/stock/{symbol}
│   ├── market.py       # /api/market/overview, /api/market/us
│   ├── webhook.py      # /api/webhook/tradingview
│   └── orders.py       # /api/orders
├── agents/
│   ├── data_agent.py   # 每日 14:30 爬蟲
│   ├── indicator.py    # 每日 15:30 指標預算
│   ├── correlation.py  # 每日 16:00 宏觀連動
│   ├── tdcc_agent.py   # 每週六 大戶集保
│   ├── signal_sim.py   # AI 替代 TradingView 信號
│   └── trading_agent.py# Claude Code Tool Use 下單
├── risk/
│   └── risk_manager.py # 六層風控
└── utils/
    ├── db.py
    ├── redis_client.py
    └── telegram.py
```

## requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
redis==5.0.4
pandas==2.2.2
pandas-ta==0.3.14b
anthropic==0.28.0
httpx==0.27.0
apscheduler==3.10.4
pydantic==2.7.1
python-dotenv==1.0.1
backtrader==1.9.78.123
requests==2.32.3
```

## main.py 骨架

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routers import stock, market, webhook, orders

app = FastAPI(title="Taiwan AI Stock Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router)
app.include_router(market.router)
app.include_router(webhook.router)
app.include_router(orders.router)

scheduler = AsyncIOScheduler(timezone="Asia/Taipei")

@app.on_event("startup")
async def startup():
    # 每日 14:30 爬取資料
    scheduler.add_job(run_data_agent, 'cron', hour=14, minute=30)
    # 每日 15:30 計算指標
    scheduler.add_job(run_indicators, 'cron', hour=15, minute=30)
    # 每日 16:00 計算宏觀連動
    scheduler.add_job(run_correlation, 'cron', hour=16, minute=0)
    # 每週六 08:00 更新大戶集保
    scheduler.add_job(run_tdcc, 'cron', day_of_week='sat', hour=8)
    scheduler.start()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Taiwan AI Stock Radar"}
```

## Data Agent（每日 14:30）

```python
# agents/data_agent.py
# 參考 whale-quant 第三章架構
# https://github.com/datawhalechina/whale-quant/blob/master/notebook/ch03/ch03.ipynb

import requests
import pandas as pd
from FinMind.data import DataLoader

dl = DataLoader()

def fetch_daily_price(symbol: str, date: str):
    """TWSE 每日行情"""
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    resp = requests.get(url, params={"stockNo": symbol, "date": date})
    # 解析並寫入 daily_price 表

def fetch_chip_data(symbol: str, start_date: str):
    """FinMind 三大法人"""
    df = dl.taiwan_stock_institutional_investors(
        stock_id=symbol,
        start_date=start_date
    )
    # 寫入 chip_data 表

def fetch_margin_data(symbol: str, start_date: str):
    """FinMind 融資融券"""
    df = dl.taiwan_stock_margin_purchase_short_sale(
        stock_id=symbol,
        start_date=start_date
    )

def fetch_branch_chip(symbol: str, date: str):
    """FinMind 券商分點"""
    df = dl.taiwan_stock_shareholding(
        stock_id=symbol,
        start_date=date
    )
    # 寫入 branch_chip_daily 表

def fetch_futures():
    """期交所期貨選擇權"""
    # 外資期貨淨部位、PCR、未平倉
    pass

def calculate_settlement_date():
    """計算當月台指期結算日（第三個週三）"""
    import calendar
    from datetime import date
    today = date.today()
    # 找當月第三個週三
    cal = calendar.monthcalendar(today.year, today.month)
    wednesdays = [w[calendar.WEDNESDAY] for w in cal if w[calendar.WEDNESDAY] != 0]
    settlement = date(today.year, today.month, wednesdays[2])
    return settlement

def run_data_agent():
    """每日 14:30 執行"""
    symbols = get_watchlist_symbols()  # 從 watchlist 表讀取
    today = date.today().strftime("%Y%m%d")
    for symbol in symbols:
        fetch_daily_price(symbol, today)
        fetch_chip_data(symbol, today)
        fetch_margin_data(symbol, today)
        fetch_branch_chip(symbol, today)
    fetch_futures()
    calculate_settlement_date()
```

## 指標預算（每日 15:30）

```python
# agents/indicator.py
import pandas as pd
import pandas_ta as ta

def run_indicators():
    """
    每日 15:30 執行，預算所有指標寫入 stock_indicators_daily
    前端 API 只做 SELECT，不即時計算
    """
    symbols = get_all_active_symbols()
    for symbol in symbols:
        df = get_price_history(symbol, days=120)

        # 技術指標
        df['rsi'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'])
        df['macd_signal'] = 'neutral'
        df.loc[macd['MACD_12_26_9'] > macd['MACDs_12_26_9'], 'macd_signal'] = 'bullish'
        df.loc[macd['MACD_12_26_9'] < macd['MACDs_12_26_9'], 'macd_signal'] = 'bearish'
        kd = ta.stoch(df['high'], df['low'], df['close'])
        df['kd_k'] = kd['STOCHk_14_3_3']
        df['kd_d'] = kd['STOCHd_14_3_3']

        # ATR(14)
        df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # 滾動 Beta(60日) vs 加權指數
        taiex = get_taiex_history(days=120)
        df['rolling_beta_60'] = df['close'].pct_change().rolling(60).cov(
            taiex['close'].pct_change()
        ) / taiex['close'].pct_change().rolling(60).var()

        # 20MA 乖離率 + 歷史百分位
        df['ma20'] = ta.sma(df['close'], length=20)
        df['ma20_bias'] = (df['close'] - df['ma20']) / df['ma20'] * 100
        df['bias_percentile'] = df['ma20_bias'].rolling(252).rank(pct=True) * 100
        df['is_overheat'] = df['bias_percentile'] > 85

        # 寫入 DB（只寫最新一筆）
        save_indicators(symbol, df.iloc[-1])
```

## 宏觀連動計算（每日 16:00）

```python
# agents/correlation.py
# 計算個股與 SOX、DXY 的 20 日滾動相關係數

def run_correlation():
    import yfinance as yf
    sox = yf.download("^SOX", period="60d")['Close']
    dxy = yf.download("DX-Y.NYB", period="60d")['Close']

    symbols = get_all_active_symbols()
    for symbol in symbols:
        df = get_price_history(symbol, days=60)
        returns = df['close'].pct_change()
        sox_returns = sox.pct_change()
        dxy_returns = dxy.pct_change()

        corr_sox = returns.rolling(20).corr(sox_returns).iloc[-1]
        corr_dxy = returns.rolling(20).corr(dxy_returns).iloc[-1]

        # 航運類股額外計算 SCFI
        if is_shipping_stock(symbol):
            scfi = get_scfi_data()
            corr_scfi = returns.rolling(20).corr(scfi.pct_change()).iloc[-1]
        else:
            corr_scfi = None

        save_correlation(symbol, corr_sox, corr_dxy, corr_scfi)
```

## Claude API 決策中心

```python
# agents/ai_engine.py
import anthropic
import redis
import json

client = anthropic.Anthropic()
redis_client = redis.Redis()

def get_ai_analysis(symbol: str) -> dict:
    """
    每日只呼叫一次，結果快取至 Redis
    TTL 到隔日 09:00
    """
    cache_key = f"ai_report:{symbol}:{today()}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    context = build_ai_context(symbol)
    result = call_claude_api(symbol, context)

    redis_client.set(cache_key, json.dumps(result), ex=57600)
    save_to_db(symbol, result)
    return result

def build_ai_context(symbol: str) -> dict:
    """從各表 SELECT，組合結構化 JSON"""
    return {
        "symbol": symbol,
        "price_data": get_latest_price(symbol),
        "technicals": get_indicators(symbol),
        "risk_metrics": {"atr_14": ..., "rolling_beta_60": ...},
        "chip_data": get_chip_data(symbol),
        "large_holders": get_large_holders(symbol),
        "macro_correlation": get_correlation(symbol),
        "calendar_events": get_upcoming_events(symbol),
        "gov_stock": get_gov_stock_data(),
        "branch_concentration": get_branch_concentration(symbol)
    }

def call_claude_api(symbol: str, context: dict) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,  # 評審團 + IC備忘錄 + 多空辯論邏輯
        messages=[{
            "role": "user",
            "content": f"請分析股票 {symbol}，資料如下：{json.dumps(context, ensure_ascii=False)}"
        }]
    )
    return parse_ai_response(response.content[0].text)
```

## TradingView Webhook 端點

```python
# routers/webhook.py
from fastapi import APIRouter, Request, HTTPException
import hmac, hashlib, json

router = APIRouter()

@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    body = await request.body()
    # 驗證簽名
    signature = request.headers.get("X-TV-Signature", "")
    expected = hmac.new(
        os.getenv("TV_WEBHOOK_SECRET").encode(),
        body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401)

    signal = json.loads(body)
    symbol = signal['symbol'].replace("TWSE:", "").replace("TW:", "")

    # 寫入 Redis 佇列 + 推播前端
    redis_client.lpush("tv_signals", json.dumps(signal))
    await websocket_manager.broadcast({"type": "tv_signal", "data": signal})
    return {"status": "received"}
```

## 六層風控

```python
# risk/risk_manager.py
class RiskManager:
    def check_all(self, symbol, action, quantity, price, account) -> bool:
        return all([
            self.check_max_loss(quantity, price, account),    # 單筆損失 ≤ 2%
            self.check_position_limit(quantity, price, account), # 單股 ≤ 10%
            self.check_daily_loss(account),                    # 當日虧損 ≤ 5%
            self.check_ai_score(symbol),                       # AI 分數 ≥ 70
            self.check_market_hours(),                         # 09:00-13:30
            self.check_settlement_risk()                       # 結算前 2天禁止
        ])
```
