# Taiwan AI Stock Radar — 07 資料來源完整說明
> Sprint 2 建立 Data Agent 前必讀

---

## 資料源總覽

| 來源 | 提供資料 | 申請難度 | 費用 | 速率限制 |
|------|------|------|------|------|
| TWSE 證交所 | 每日行情、三大法人、融資券、全市場股票清單 | 無需申請 | 免費 | 每5秒3次，超過會被ban |
| TWSE OpenAPI | 前一日收盤資料、結構化 JSON | 無需申請 | 免費 | 較寬鬆 |
| TWSE MIS 即時 | 盤中即時報價（5秒更新）| 無需申請 | 免費 | 每5秒3次 |
| TPEx 櫃買中心 | OTC 股票行情 | 無需申請 | 免費 | 同 TWSE |
| TAIFEX 期交所 | 期貨選擇權、外資淨部位、PCR | 無需申請 | 免費 | 無明確限制 |
| FinMind | 券商分點、籌碼、財報、歷史行情 | 需註冊 | 免費300次/hr，登入後600次/hr | 600次/hr（登入後）|
| TDCC 集保 | 大戶持股分佈（週更）| 無需申請 | 免費 | 無明確限制 |
| yfinance | 美股指數、SOX、DXY、個股歷史 | pip install | 免費 | 非官方，不穩定 |
| Yahoo Finance | 美股即時報價備援 | 無需申請 | 免費 | 有封鎖風險 |

---

## 一、TWSE 證交所

### 1-A 每日收盤行情（官網 API，有當天資料）

```python
import requests
import pandas as pd

def fetch_twse_daily(stock_id: str, date: str) -> pd.DataFrame:
    """
    date 格式：YYYYMMDD，例如 20260601
    注意：只能查單一股票的月份資料
    """
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {
        "response": "json",
        "stockNo": stock_id,
        "date": date  # 抓該月份所有交易日
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()

    if data.get('stat') != 'OK':
        return pd.DataFrame()

    df = pd.DataFrame(data['data'], columns=data['fields'])
    df.columns = ['date','volume','turnover','open','high','low','close','change','transactions']
    # 清洗數字欄位（移除逗號）
    for col in ['volume','open','high','low','close']:
        df[col] = df[col].str.replace(',','').astype(float)
    return df
```

### 1-B 全市場股票清單（一次取得所有上市股票）

```python
def fetch_all_stocks() -> pd.DataFrame:
    """取得所有上市股票代號與名稱"""
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
    params = {"response": "open_data"}
    df = pd.read_csv(url)
    return df[['證券代號', '證券名稱']]
```

### 1-C OpenAPI（前一日資料，結構更穩定）

```python
def fetch_twse_openapi(stock_id: str) -> dict:
    """
    openapi.twse.com.tw → 前一日收盤資料
    適合每日收盤後批次更新
    """
    url = f"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
    resp = requests.get(url)
    data = resp.json()
    # 過濾目標股票
    result = [d for d in data if d.get('Code') == stock_id]
    return result[0] if result else {}
```

### 1-D 盤中即時報價（5秒更新）

```python
def fetch_realtime_quote(stock_id: str) -> dict:
    """
    mis.twse.com.tw → 盤中即時五檔報價
    注意：每5秒最多3個 request，超過被ban
    """
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
    params = {
        "ex_ch": f"tse_{stock_id}.tw",
        "json": "1",
        "delay": "0"
    }
    resp = requests.get(url, params=params)
    data = resp.json()

    if not data.get('msgArray'):
        return {}

    stock = data['msgArray'][0]
    return {
        "symbol": stock_id,
        "name": stock.get('n'),
        "price": float(stock.get('z', 0)),    # 成交價
        "open": float(stock.get('o', 0)),     # 開盤
        "high": float(stock.get('h', 0)),     # 最高
        "low": float(stock.get('l', 0)),      # 最低
        "volume": int(stock.get('v', 0)),     # 成交量（張）
        "bid": stock.get('b'),                # 最佳買價
        "ask": stock.get('a'),                # 最佳賣價
        "limit_up": float(stock.get('u', 0)), # 漲停價
        "limit_dn": float(stock.get('w', 0)), # 跌停價
    }
```

### 1-E 三大法人（TWSE 直接爬）

```python
def fetch_institutional_twse(date: str) -> pd.DataFrame:
    """
    date 格式：YYYYMMDD
    """
    url = "https://www.twse.com.tw/fund/T86"
    params = {
        "response": "json",
        "date": date,
        "selectType": "ALL"
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    df = pd.DataFrame(data.get('data', []), columns=data.get('fields', []))
    return df
```

---

## 二、TPEx 櫃買中心

```python
def fetch_tpex_daily(stock_id: str, date: str) -> pd.DataFrame:
    """OTC 上櫃股票每日行情"""
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    resp = requests.get(url)
    data = resp.json()
    result = [d for d in data if d.get('SecuritiesCompanyCode') == stock_id]
    return pd.DataFrame(result)
```

---

## 三、TAIFEX 期交所

```python
def fetch_futures_institutional(date: str) -> dict:
    """外資期貨未平倉（大台、小台）"""
    url = "https://www.taifex.com.tw/cht/3/futContractsDate"
    # 期交所需要 POST + 特定 form data
    form_data = {
        "queryStartDate": date,
        "queryEndDate": date,
        "commodityId": "TX"  # TX=大台指
    }
    resp = requests.post(url, data=form_data)
    # 解析 HTML table
    df = pd.read_html(resp.text)[0]
    return df

def fetch_options_pcr(date: str) -> dict:
    """選擇權 Put/Call Ratio"""
    url = "https://www.taifex.com.tw/cht/3/callsAndPutsDate"
    form_data = {"queryStartDate": date, "queryEndDate": date}
    resp = requests.post(url, data=form_data)
    df = pd.read_html(resp.text)[0]
    # 計算 PCR = Put OI / Call OI
    return df

def calculate_settlement_date(year: int, month: int) -> date:
    """台指期結算日 = 每月第三個週三"""
    import calendar
    cal = calendar.monthcalendar(year, month)
    wednesdays = [w[calendar.WEDNESDAY] for w in cal if w[calendar.WEDNESDAY] != 0]
    return date(year, month, wednesdays[2])
```

---

## 四、FinMind（需註冊取得 Token）

### 申請步驟
```
1. 前往 https://finmindtrade.com/
2. 點選「註冊」→ 填入 Email 並驗證
3. 登入後到個人頁面取得 API Token
4. 填入 .env：FINMIND_TOKEN=your_token_here
免費：300 次/hr（未登入）→ 600 次/hr（登入後）
付費方案：更高頻率，約 NT$300+/月
```

### 安裝
```bash
pip install FinMind --break-system-packages
```

### 初始化

```python
from FinMind.data import DataLoader
import os

dl = DataLoader()
dl.login_by_token(api_token=os.getenv("FINMIND_TOKEN"))
```

### 每日股價歷史

```python
def fetch_finmind_price(stock_id: str, start_date: str) -> pd.DataFrame:
    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date  # 格式：YYYY-MM-DD
    )
    return df  # 欄位：date, stock_id, Trading_Volume, open, max, min, close, spread, Trading_Turnover
```

### 三大法人

```python
def fetch_institutional_finmind(stock_id: str, start_date: str) -> pd.DataFrame:
    df = dl.taiwan_stock_institutional_investors(
        stock_id=stock_id,
        start_date=start_date
    )
    # 欄位：date, stock_id, name（外資/投信/自營商）, buy, sell
    return df
```

### 融資融券

```python
def fetch_margin_finmind(stock_id: str, start_date: str) -> pd.DataFrame:
    df = dl.taiwan_stock_margin_purchase_short_sale(
        stock_id=stock_id,
        start_date=start_date
    )
    # 欄位：date, MarginPurchase（融資買進）, ShortSale（融券賣出）等
    return df
```

### 券商分點（核心功能）

```python
def fetch_branch_chip(stock_id: str, date: str) -> pd.DataFrame:
    """
    dataset: TaiwanStockTradingDailyReport
    取得當日買超/賣超前N大券商分點
    """
    import requests
    url = "https://api.finmindtrade.com/api/v4/taiwan_stock_trading_daily_report"
    headers = {"Authorization": f"Bearer {os.getenv('FINMIND_TOKEN')}"}
    params = {"data_id": stock_id, "date": date}
    resp = requests.get(url, headers=headers, params=params)
    df = pd.DataFrame(resp.json()['data'])
    # 欄位：date, stock_id, broker_id, broker_name, buy, sell
    # 計算淨買超
    df['net'] = df['buy'] - df['sell']
    return df.sort_values('net', ascending=False)
```

### 計算籌碼集中度

```python
def calc_branch_concentration(stock_id: str, date: str) -> float:
    """前10大買超分點合計佔當日總成交量比例"""
    df = fetch_branch_chip(stock_id, date)
    top10_buy = df.nlargest(10, 'buy')['buy'].sum()
    total_volume = get_daily_volume(stock_id, date)
    return round(top10_buy / total_volume * 100, 2)
```

### 財報資料

```python
def fetch_financial_report(stock_id: str) -> pd.DataFrame:
    df = dl.taiwan_stock_financial_statement(
        stock_id=stock_id,
        start_date="2020-01-01"
    )
    return df  # 含 ROE、EPS、營收等季報資料
```

### 法說會與除息行事曆

```python
def fetch_dividend_info(stock_id: str) -> pd.DataFrame:
    """除權息資料"""
    df = dl.taiwan_stock_dividend(start_date="2026-01-01")
    return df[df['stock_id'] == stock_id]

def fetch_monthly_revenue(stock_id: str, start_date: str) -> pd.DataFrame:
    """每月營收（約每月10日公布）"""
    df = dl.taiwan_stock_month_revenue(
        stock_id=stock_id,
        start_date=start_date
    )
    return df
```

---

## 五、TDCC 集保結算所（大戶持股週更）

```python
def fetch_large_holders(stock_id: str, date: str) -> dict:
    """
    每週六更新，date 為當週最後一個交易日
    URL 格式需帶入股票代號與日期
    """
    url = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
    # TDCC 需要模擬表單送出
    form_data = {
        "scaDates": date.replace("-",""),  # YYYYMMDD
        "scaDate": date.replace("-",""),
        "SqlMethod": "StockNo",
        "StockNo": stock_id,
        "REQ_OPR": "SELECT"
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
    }
    session = requests.Session()
    resp = session.post(url, data=form_data, headers=headers)
    df = pd.read_html(resp.text)[0]

    # 解析 400張以上、1000張以上人數與比例
    result = {}
    for _, row in df.iterrows():
        if '400' in str(row[0]) and '999' not in str(row[0]):
            result['holders_over_400'] = int(str(row[1]).replace(',',''))
            result['percent_over_400'] = float(str(row[2]).replace('%',''))
        if '1000' in str(row[0]):
            result['holders_over_1000'] = int(str(row[1]).replace(',',''))
            result['percent_over_1000'] = float(str(row[2]).replace('%',''))
    return result
```

---

## 六、yfinance（美股 + 宏觀指數）

```bash
pip install yfinance --break-system-packages
```

```python
import yfinance as yf

# 美股三大指數
def fetch_us_indices() -> dict:
    tickers = {
        "sp500":  "^GSPC",   # S&P 500
        "nasdaq": "^NDX",    # Nasdaq 100
        "dji":    "^DJI",    # 道瓊
        "sox":    "^SOX",    # 費城半導體
        "vix":    "^VIX",    # 恐慌指數
        "dxy":    "DX-Y.NYB" # 美元指數
    }
    result = {}
    for name, ticker in tickers.items():
        data = yf.Ticker(ticker).fast_info
        result[name] = {
            "last_price": data.last_price,
            "previous_close": data.previous_close,
            "change_pct": (data.last_price - data.previous_close) / data.previous_close * 100
        }
    return result

# 美股科技個股（熱力圖用）
def fetch_us_tech_stocks() -> list:
    symbols = ["NVDA", "AMD", "TSM", "MSFT", "AVGO", "GOOGL", "ASML", "AMAT", "META"]
    result = []
    for sym in symbols:
        info = yf.Ticker(sym).fast_info
        result.append({
            "symbol": sym,
            "price": info.last_price,
            "change_pct": (info.last_price - info.previous_close) / info.previous_close * 100
        })
    return result

# 歷史資料（宏觀連動計算用）
def fetch_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y
    """
    return yf.download(ticker, period=period, auto_adjust=True)
```

---

## 七、八大官股資料

TWSE 沒有直接提供八大官股 API，需透過 FinMind 的 broker_id 過濾：

```python
# 八大官股券商代號
GOV_BROKERS = {
    "1020": "台灣銀行",
    "1030": "土地銀行",
    "1040": "合作金庫",
    "1050": "第一銀行",
    "1060": "華南銀行",
    "1070": "彰化銀行",
    "1080": "台灣企銀",
    "1090": "兆豐銀行"
}

def fetch_gov_stock_activity(stock_id: str, date: str) -> dict:
    """計算八大官股當日買賣超合計"""
    df = fetch_branch_chip(stock_id, date)
    gov_df = df[df['broker_id'].isin(GOV_BROKERS.keys())]
    total_net = gov_df['net'].sum()
    return {
        "total_net_buy": total_net,
        "is_buying": total_net > 0,
        "detail": gov_df[['broker_name','net']].to_dict('records')
    }
```

---

## 八、注意事項與限制

| 來源 | 主要風險 | 對策 |
|------|------|------|
| TWSE MIS 即時 | 每5秒3次，超過被 ban IP | Redis 快取 + 限速器 |
| FinMind 免費版 | 600次/hr 上限 | Pre-aggregation，只在收盤後批次爬取 |
| yfinance | 非官方 API，Yahoo 可能封鎖 | 加 retry 機制，備援用 Alpha Vantage |
| TDCC | 需模擬 Session，格式可能改版 | 錯誤通知，人工確認 |
| TAIFEX | POST 表單爬蟲，結構較複雜 | 定期驗證爬蟲正確性 |

## 九、爬蟲排程總覽

```python
# 每日排程（apscheduler）
scheduler.add_job(fetch_all_daily_data,   'cron', hour=14, minute=35)  # 收盤後
scheduler.add_job(run_indicator_calc,     'cron', hour=15, minute=30)  # 指標預算
scheduler.add_job(run_correlation_calc,   'cron', hour=16, minute=0)   # 宏觀連動
scheduler.add_job(fetch_us_data,          'cron', hour=7,  minute=0)   # 美股昨收（早上）
scheduler.add_job(fetch_tdcc_weekly,      'cron', day_of_week='sat', hour=8)  # 週六集保

# 盤中（WebSocket 推播用，選擇性）
scheduler.add_job(fetch_realtime_index,   'interval', seconds=30)  # 大盤指數
```

## 十、Token 與金鑰管理

所有金鑰存在 `.env`，絕不 commit 到 Git：

```bash
# .gitignore 必須包含
.env
*.env
```

```python
# 統一從環境變數讀取
from dotenv import load_dotenv
load_dotenv()

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TV_WEBHOOK_SECRET = os.getenv("TV_WEBHOOK_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```
