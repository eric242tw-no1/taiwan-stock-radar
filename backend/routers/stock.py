from fastapi import APIRouter
from services.stock_quote_fetcher import fetch_stock_quote
from services.ohlcv_service import fetch_ohlcv
from services.finmind_fetcher import fetch_stock_chip, fetch_margin
from services.indicator_service import get_indicators
from services.ai_analysis_service import get_ai_analysis
from services.ptt_sentiment import get_ptt_sentiment
from services.cmoney_sentiment import get_cmoney_sentiment

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/{symbol}/quote")
async def get_stock_quote(symbol: str):
    """
    個股即時報價：價格、漲跌、成交量、量比
    資料來源：TWSE MIS（盤中每10秒更新）
    symbol: 股票代號，如 2330（不含 .TW）
    """
    return fetch_stock_quote(symbol.upper())


@router.get("/{symbol}/chip")
async def get_stock_chip(symbol: str):
    """
    個股籌碼：三大法人買賣超（10日）+ 融資融券餘額
    資料來源：FinMind
    """
    chip = fetch_stock_chip(symbol.upper())
    margin = fetch_margin(symbol.upper())

    # 法人：整理最近5個交易日每天的外資/投信/自營
    rows = chip.get("data", [])
    dates = sorted(set(r["date"] for r in rows))[-5:]
    daily = []
    for d in dates:
        day_rows = [r for r in rows if r["date"] == d]
        net: dict[str, int] = {"foreign": 0, "trust": 0, "dealer": 0}
        for r in day_rows:
            from services.finmind_fetcher import NAME_MAP
            key = NAME_MAP.get(r["name"])
            if key:
                net[key] += int(r["buy"]) - int(r["sell"])
        daily.append({"date": d, **net})

    return {
        "symbol":    symbol.upper(),
        "latest":    chip.get("latest", {}),
        "daily":     daily,
        "margin":    margin,
    }


@router.get("/{symbol}/ohlcv")
async def get_stock_ohlcv(symbol: str, period: str = "90d"):
    """
    日K OHLCV：period 支援 90d / 180d / 1y / 2y
    資料來源：yfinance，1小時快取
    """
    ticker = f"{symbol.upper()}.TW"
    bars = fetch_ohlcv(ticker, period)
    return {"symbol": symbol, "period": period, "bars": bars}


@router.get("/{symbol}/ai-analysis")
async def get_stock_ai_analysis(symbol: str):
    """
    個股 AI 評分：Claude 分析技術 + 籌碼 + 報價，結果快取到 Redis（TTL 至隔日 09:00）
    若 ANTHROPIC_API_KEY 未設，回傳 source=rule_based（前端自行計算）
    """
    sym = symbol.upper()
    ticker = f"{sym}.TW"

    ind  = get_indicators(ticker)
    chip_data = None
    try:
        from services.finmind_fetcher import fetch_stock_chip, fetch_margin
        chip_raw  = fetch_stock_chip(sym)
        margin    = fetch_margin(sym)
        rows = chip_raw.get("data", [])
        dates = sorted(set(r["date"] for r in rows))
        latest_net: dict[str, int] = {"foreign": 0, "trust": 0, "dealer": 0}
        if dates:
            last_date = dates[-1]
            from services.finmind_fetcher import NAME_MAP
            for r in rows:
                if r["date"] == last_date:
                    key = NAME_MAP.get(r["name"])
                    if key:
                        latest_net[key] += int(r["buy"]) - int(r["sell"])
        chip_data = {"latest": latest_net, "margin": margin}
    except Exception:
        pass

    quote = None
    try:
        quote = fetch_stock_quote(sym)
    except Exception:
        pass

    result = get_ai_analysis(sym, ind, chip_data, quote)

    if not result:
        return {"symbol": sym, "source": "rule_based"}

    return {"symbol": sym, **result}


@router.get("/{symbol}/sentiment")
async def get_stock_sentiment(symbol: str):
    """
    個股論壇情緒：PTT Stock 板 + CMoney 個股討論區
    資料來源：PTT（靜態爬蟲，30分鐘快取）+ CMoney（Playwright，30分鐘快取）
    CMoney 爬取失敗時回傳 null，前端不顯示該區塊
    """
    sym = symbol.upper()
    ptt = get_ptt_sentiment(sym)
    cmoney = get_cmoney_sentiment(sym)
    return {"symbol": sym, "ptt": ptt, "cmoney": cmoney}
