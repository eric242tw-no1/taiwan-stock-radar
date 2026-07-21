import logging
from fastapi import APIRouter
from services.stock_quote_fetcher import fetch_stock_quote
from services.ohlcv_service import fetch_ohlcv
from services.finmind_fetcher import fetch_stock_chip, fetch_margin
from services.ptt_sentiment import get_ptt_sentiment
from services.cmoney_sentiment import get_cmoney_sentiment
from services.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/{symbol}/quote")
async def get_stock_quote(symbol: str):
    """
    個股即時報價：價格、漲跌、成交量、量比
    資料來源：TWSE MIS（盤中每10秒更新）
    symbol: 股票代號，如 2330（不含 .TW）
    """
    sym = symbol.upper()
    cached = cache.get(f"quote:{sym}")
    if cached:
        return cached
    result = fetch_stock_quote(sym)
    cache.set(f"quote:{sym}", result, ttl=10)
    return result


@router.get("/{symbol}/chip")
async def get_stock_chip(symbol: str):
    """
    個股籌碼：三大法人買賣超（10日）+ 融資融券餘額
    資料來源：FinMind
    """
    sym = symbol.upper()
    cached = cache.get(f"chip:{sym}")
    if cached:
        return cached

    chip = fetch_stock_chip(sym)
    margin = fetch_margin(sym)

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

    result = {
        "symbol":    sym,
        "latest":    chip.get("latest", {}),
        "daily":     daily,
        "margin":    margin,
    }
    cache.set(f"chip:{sym}", result)
    return result


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
    個股 AI 深度分析：10位分析師評審 + IC備忘錄 + 情景目標價 + 進出場建議
    資料來源：FinMind 120日行情 + 籌碼，模型：Claude Sonnet
    快取到隔日 09:00；無 API Key 回傳 source=rule_based
    """
    sym = symbol.upper()
    try:
        from agents.ai_engine import get_ai_analysis
        result = await get_ai_analysis(sym, force=False)
        if not result:
            return {"symbol": sym, "source": "rule_based"}
        return {"symbol": sym, **result}
    except Exception as e:
        logger.error("AI analysis failed [%s]: %s", sym, e)
        return {"symbol": sym, "source": "rule_based", "error": str(e)}


@router.get("/{symbol}/chip-distribution")
async def get_chip_distribution(symbol: str):
    """
    TDCC 集保分布：各持股級距佔比（週更新）
    資料來源：FinMind TaiwanStockHolding
    """
    from services.tdcc_fetcher import get_chip_distribution
    data = get_chip_distribution(symbol.upper())
    return {"symbol": symbol.upper(), "distribution": data}


@router.get("/{symbol}/ai-score")
async def get_stock_ai_score(symbol: str):
    """
    快取讀取 AI 評分：直接從 Redis 讀取當日快取，未命中回傳 null score。
    不觸發新的 Claude API 呼叫，適合輪詢/輕量讀取。
    """
    sym = symbol.upper()
    try:
        from agents.ai_engine import _cache_get, _cache_key
        import json
        cached = await _cache_get(_cache_key(sym))
        if cached:
            data = json.loads(cached)
            return {
                "symbol": sym,
                "score": data.get("score"),
                "action": data.get("action"),
                "summary": data.get("summary"),
                "cached": True,
            }
        return {"symbol": sym, "score": None, "cached": False}
    except Exception as e:
        logger.error("AI score cache read failed [%s]: %s", sym, e)
        return {"symbol": sym, "score": None, "cached": False, "error": str(e)}


@router.get("/{symbol}/sentiment")
async def get_stock_sentiment(symbol: str):
    """
    個股論壇情緒：PTT Stock 板 + CMoney 個股討論區
    資料來源：PTT（靜態爬蟲，30分鐘快取）+ CMoney（Playwright，30分鐘快取）
    CMoney 爬取失敗時回傳 null，前端不顯示該區塊
    """
    sym = symbol.upper()
    name = None
    try:
        q = fetch_stock_quote(sym)
        name = q.get("name") if q else None
    except Exception:
        pass
    ptt = get_ptt_sentiment(sym, name=name)
    cmoney = get_cmoney_sentiment(sym)
    return {"symbol": sym, "ptt": ptt, "cmoney": cmoney}
