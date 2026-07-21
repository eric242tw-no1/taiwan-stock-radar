import time  # noqa
from typing import Optional
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query
import asyncio
from services.data_fetcher import get_cached_us_indices, get_cache_meta
from services.twse_fetcher import get_cached_tw_market, get_tw_cache_meta
from services.taifex_fetcher import get_cached_futures_and_fx, get_futures_cache_meta
from services.finmind_fetcher import get_cached_chip, get_chip_cache_meta
from services.indicator_service import get_indicators, get_all_indicators, calculate_and_store
from services.ohlcv_service import fetch_ohlcv
from services.sector_fetcher import get_cached_sectors, fetch_sectors
from services.gov_fund_fetcher import get_cached_gov_funds
from services.fear_greed_fetcher import get_cached_fear_greed
from services.buffett_fetcher import get_cached_buffett, fetch_buffett
from services.cache import cache
from services.stock_quote_fetcher import fetch_stock_quote

router = APIRouter(prefix="/api/market", tags=["market"])

# ── 追蹤股票清單 ──────────────────────────────────────────────────
TRACKED_SYMBOLS = [
    "2330.TW","2317.TW","2454.TW","0050.TW","2308.TW","2382.TW",
    "2379.TW","3661.TW","6669.TW","4968.TW","2412.TW","2881.TW",
    "2303.TW","2002.TW","1301.TW","3008.TW","2886.TW","2891.TW",
]

STOCK_NAMES = {
    "2330":"台積電","2317":"鴻海","2454":"聯發科","0050":"元大50",
    "2308":"台達電","2382":"廣達","2379":"瑞昱","3661":"世芯-KY",
    "6669":"緯穎","4968":"立積","2412":"中華電","2881":"富邦金",
    "2303":"聯電","2002":"中鋼","1301":"台塑","3008":"大立光",
    "2886":"兆豐金","2891":"中信金",
}

# ── 簡單記憶體快取 ────────────────────────────────────────────────
_top_movers_cache: dict = {"ts": 0, "data": []}
_leaders_cache:    dict = {"ts": 0, "data": []}


@router.get("/us-indices")
async def get_us_indices():
    """
    美股四大指標：S&P500、Nasdaq、道瓊、VIX
    資料來源：yfinance，每5分鐘更新快取
    VIX 含 level/label/color 分級
    """
    data = get_cached_us_indices()
    meta = get_cache_meta()
    return {**data, "_meta": meta}


@router.get("/futures-fx")
async def get_futures_fx():
    """
    大台期近月合約 + USD/TWD 即時匯率
    資料來源：TAIFEX MIS + yfinance TWD=X
    每分鐘更新快取
    """
    data = get_cached_futures_and_fx()
    meta = get_futures_cache_meta()
    return {**data, "_meta": meta}


@router.get("/tw")
async def get_tw_market():
    """
    台股市場即時資料：加權指數、OTC 櫃買指數、漲跌家數
    資料來源：TWSE MIS（盤中即時）+ afterTrading MI_INDEX（漲跌家數）
    每5秒更新（MIS限制5秒3次）
    """
    data = get_cached_tw_market()
    meta = get_tw_cache_meta()
    return {**data, "_meta": meta}


@router.get("/indicators")
async def get_all_indicators_endpoint():
    """
    所有追蹤股票的最新技術指標（RSI/MACD/KD/ATR）
    資料來源：yfinance + pandas-ta，每日15:05更新
    """
    return {"data": get_all_indicators()}


@router.post("/indicators/refresh")
async def trigger_indicator_refresh():
    """手動觸發技術指標計算（開發/測試用）"""
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, calculate_and_store)
    return {"status": "triggered", "message": "indicator calculation started in background"}


@router.get("/indicators/{ticker}")
async def get_indicator(ticker: str):
    """
    單一股票技術指標。ticker 格式：2330.TW
    回應包含 patterns 欄位（K 線形態識別，最近 5 根）
    """
    t = ticker.upper()
    cached = cache.get(f"indicators:{t}")
    if cached:
        return cached

    data = get_indicators(t)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No indicator data for {ticker}")

    # K 線形態識別（最近 5 根）
    try:
        import yfinance as yf
        from services.candlestick import detect_from_ohlcv
        df = await asyncio.to_thread(yf.download, t, period="14d", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            rows = df.tail(5).reset_index().to_dict("records")
            data["patterns"] = detect_from_ohlcv(rows)
        else:
            data["patterns"] = []
    except Exception:
        data["patterns"] = []

    # 主力意圖四階段分析
    try:
        from services.market_maker import detect_phase
        from services.finmind_fetcher import fetch_stock_chip
        symbol_raw = t.replace(".TW", "")
        chip_raw = await asyncio.to_thread(fetch_stock_chip, symbol_raw)
        chip_data = chip_raw.get("latest", {})
        data["market_maker_intent"] = detect_phase(chip_data, data)
    except Exception:
        data["market_maker_intent"] = {"phase": "觀望", "confidence": 0.0, "signals": []}

    cache.set(f"indicators:{t}", data)
    return data


@router.get("/ohlcv/{ticker}")
async def get_ohlcv(ticker: str, period: str = "90d"):
    """
    日K OHLCV資料。ticker 格式：2330.TW，period 例：90d / 180d / 1y
    資料來源：yfinance，1小時快取
    """
    bars = fetch_ohlcv(ticker.upper(), period)
    return {"ticker": ticker, "period": period, "bars": bars}


@router.get("/screen")
async def screen_stocks(
    rsi_min: float | None = None,
    rsi_max: float | None = None,
    macd_cross: str | None = None,   # "golden" | "death"
    kd_cross: str | None = None,     # "golden" | "death"
    kd_min: float | None = None,
    kd_max: float | None = None,
    atr_pct_max: float | None = None,
):
    """
    選股篩選器：從所有追蹤股票的最新指標做條件過濾
    - rsi_min / rsi_max: RSI 範圍
    - macd_cross: "golden"=MACD hist>0, "death"=hist<0
    - kd_cross: "golden"=K>D, "death"=K<D
    - kd_min / kd_max: K 值範圍
    - atr_pct_max: ATR% 上限（波動度過濾）
    """
    all_ind = get_all_indicators()
    results = []
    for item in all_ind.values():
        rsi  = item.get("rsi14")  or 0
        macd_h = item.get("macd_hist") or 0
        k    = item.get("k")      or 0
        d    = item.get("d")      or 0
        close = item.get("close") or 0
        atr  = item.get("atr14") or 0
        atr_pct = (atr / close * 100) if close > 0 else 0

        if rsi_min is not None and rsi < rsi_min: continue
        if rsi_max is not None and rsi > rsi_max: continue
        if macd_cross == "golden" and macd_h <= 0: continue
        if macd_cross == "death"  and macd_h >= 0: continue
        if kd_cross == "golden" and k <= d: continue
        if kd_cross == "death"  and k >= d: continue
        if kd_min is not None and k < kd_min: continue
        if kd_max is not None and k > kd_max: continue
        if atr_pct_max is not None and atr_pct > atr_pct_max: continue

        results.append({**item, "atr_pct": round(atr_pct, 2)})

    # 依 RSI 排序
    results.sort(key=lambda x: x.get("rsi14") or 0, reverse=True)
    return {"count": len(results), "results": results}


@router.get("/chip")
async def get_chip_summary():
    """
    三大法人買賣超彙總（台積電/鴻海/聯發科/中華電代表性權值股）
    資料來源：FinMind TaiwanStockInstitutionalInvestorsBuySell
    每日14:30更新一次（收盤後）
    """
    data = get_cached_chip()
    meta = get_chip_cache_meta()
    return {**data, "_meta": meta}


@router.get("/top-movers")
async def get_top_movers(limit: int = 5, codes: Optional[str] = Query(None)):
    """
    漲幅排行：從追蹤股票清單批量拉即時報價，按漲幅排序
    快取 60 秒。codes 為逗號分隔的股票代碼（不含 .TW），例：2330,2317,2454
    """
    global _top_movers_cache
    symbols = ([f"{c.strip()}.TW" for c in codes.split(",") if c.strip()] if codes else TRACKED_SYMBOLS)
    cache_key = codes or ""
    # invalidate cache when stock pool changes
    if (time.time() - _top_movers_cache["ts"] < 60
            and _top_movers_cache["data"]
            and _top_movers_cache.get("pool_key") == cache_key):
        return {"results": _top_movers_cache["data"][:limit]}

    results = []
    try:
        tickers = await asyncio.to_thread(yf.Tickers, " ".join(symbols))
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                info = t.fast_info
                price      = float(info.last_price or 0)
                prev_close = float(info.previous_close or 0)
                if prev_close > 0 and price > 0:
                    chg_pct = (price - prev_close) / prev_close * 100
                    code = sym.replace(".TW", "")
                    # ponytail: fallback to TWSE MIS for name when STOCK_NAMES misses
                    name = STOCK_NAMES.get(code)
                    if not name:
                        try:
                            q = await asyncio.to_thread(fetch_stock_quote, code)
                            name = q.get("name", "") or code
                        except Exception:
                            name = code
                    results.append({
                        "code":     code,
                        "name":     name,
                        "price":    round(price, 2),
                        "chg_pct":  round(chg_pct, 2),
                    })
            except Exception:
                pass
    except Exception:
        pass

    results.sort(key=lambda x: x["chg_pct"], reverse=True)
    _top_movers_cache = {"ts": time.time(), "data": results, "pool_key": cache_key}
    return {"results": results[:limit]}


@router.get("/leaders")
async def get_leaders(limit: int = 5, codes: Optional[str] = Query(None)):
    """
    波段領頭羊：從技術指標庫計算 AI 評分，篩選多頭訊號股
    快取 60 秒。codes 為逗號分隔的股票代碼（不含 .TW），例：2330,2317,2454
    """
    global _leaders_cache
    cache_key = codes or ""
    if (time.time() - _leaders_cache["ts"] < 60
            and _leaders_cache["data"]
            and _leaders_cache.get("pool_key") == cache_key):
        return {"results": _leaders_cache["data"][:limit]}

    all_ind = get_all_indicators()
    # filter by requested codes when provided
    if codes:
        wanted = {f"{c.strip()}.TW" for c in codes.split(",") if c.strip()}
        all_ind = {k: v for k, v in all_ind.items() if k in wanted}
    scored = []
    for item in all_ind.values():
        rsi      = float(item.get("rsi14")    or 0)
        macd_h   = float(item.get("macd_hist") or 0)
        k        = float(item.get("k")        or 0)
        d        = float(item.get("d")        or 0)
        close    = float(item.get("close")    or 0)
        atr      = float(item.get("atr14")    or 0)
        atr_pct  = (atr / close * 100) if close > 0 else 0

        # 只取多頭訊號
        if rsi < 45 or macd_h <= 0:
            continue

        # 簡易 AI 綜合評分（對齊前端 computeComposite 邏輯）
        tech = min(100, max(0,
            (rsi - 30) / 40 * 40 +
            (20 if macd_h > 0 else 0) +
            (20 if k > d else 0) +
            (20 if k < 80 else 10)
        ))
        risk  = max(0, 100 - atr_pct * 10)
        macro = 50   # 固定中性
        score = round(tech * 0.5 + risk * 0.2 + macro * 0.1 + 70 * 0.2)

        ticker = item.get("ticker", "")
        code   = ticker.replace(".TW", "")
        scored.append({
            "code":    code,
            "name":    STOCK_NAMES.get(code, code),
            "score":   min(99, score),
            "rsi":     round(rsi, 1),
            "macd_h":  round(macd_h, 2),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    _leaders_cache = {"ts": time.time(), "data": scored, "pool_key": cache_key}
    return {"results": scored[:limit]}


US_HEAT_TICKERS = [
    ("NVDA",    "NVDA",    "NVIDIA"),
    ("AMD",     "AMD",     "AMD"),
    ("TSM",     "TSM",     "台積電ADR"),
    ("MSFT",    "MSFT",    "Microsoft"),
    ("AVGO",    "AVGO",    "Broadcom"),
    ("GOOGL",   "GOOGL",   "Alphabet"),
    ("ASML",    "ASML",    "ASML"),
    ("AMAT",    "AMAT",    "應用材料"),
    ("META",    "META",    "Meta"),
    ("AAPL",    "AAPL",    "Apple"),
    ("AMZN",    "AMZN",    "Amazon"),
    ("QCOM",    "QCOM",    "高通"),
    ("BTC-USD", "BTC",     "Bitcoin/USD"),
]

_us_stocks_cache: dict = {"ts": 0, "data": []}

@router.get("/us-stocks")
async def get_us_stocks():
    """
    美股科技熱力圖 + BTC/USD：13 檔即時漲跌幅
    資料來源：yfinance，快取5分鐘
    """
    global _us_stocks_cache
    if time.time() - _us_stocks_cache["ts"] < 300 and _us_stocks_cache["data"]:
        return {"stocks": _us_stocks_cache["data"]}

    symbols = [t[0] for t in US_HEAT_TICKERS]
    try:
        raw = await asyncio.to_thread(yf.download, symbols, period="5d", interval="1d", progress=False, auto_adjust=True, group_by="ticker")
        result = []
        for sym, label, full_name in US_HEAT_TICKERS:
            try:
                closes = raw[sym]["Close"].dropna() if len(symbols) > 1 else raw["Close"].dropna()
                if len(closes) < 2:
                    continue
                prev, last = float(closes.iloc[-2]), float(closes.iloc[-1])
                chg = round((last - prev) / prev * 100, 2)
                # BTC 顯示整數價格，股票顯示 2 位小數
                price = round(last, 0) if sym == "BTC-USD" else round(last, 2)
                result.append({
                    "label": label, "full_name": full_name,
                    "symbol": sym, "chg": chg, "price": price,
                    "is_crypto": sym == "BTC-USD",
                })
            except Exception:
                continue
        _us_stocks_cache = {"ts": time.time(), "data": result}
        return {"stocks": result}
    except Exception as e:
        return {"stocks": _us_stocks_cache.get("data", []), "error": str(e)}


MEMORY_STOCKS = [
    ("2408.TW", "南亞科"),
    ("2344.TW", "華邦電"),
    ("2337.TW", "旺宏"),
    ("3260.TW", "威剛"),
    ("4919.TW", "新唐"),
]

_memory_cache: dict = {"ts": 0, "data": []}

@router.get("/memory-stocks")
async def get_memory_stocks():
    """記憶體族群即時漲跌（yfinance），快取5分鐘"""
    global _memory_cache
    if time.time() - _memory_cache["ts"] < 300 and _memory_cache["data"]:
        return {"stocks": _memory_cache["data"]}

    symbols = [s[0] for s in MEMORY_STOCKS]
    name_map = {s[0]: s[1] for s in MEMORY_STOCKS}
    try:
        raw = yf.download(symbols, period="5d", interval="1d", progress=False, auto_adjust=True, group_by="ticker")
        result = []
        for sym, name in MEMORY_STOCKS:
            try:
                closes = raw[sym]["Close"].dropna() if len(symbols) > 1 else raw["Close"].dropna()
                if len(closes) < 2:
                    continue
                prev, last = float(closes.iloc[-2]), float(closes.iloc[-1])
                chg = round((last - prev) / prev * 100, 2)
                code = sym.replace(".TW", "")
                result.append({"code": code, "name": name, "price": round(last, 2), "chg": chg})
            except Exception:
                continue
        _memory_cache = {"ts": time.time(), "data": result}
        return {"stocks": result}
    except Exception as e:
        return {"stocks": _memory_cache.get("data", []), "error": str(e)}


@router.get("/sectors")
async def get_sectors():
    """
    台股產業指數漲跌幅（TWSE MI_INDEX type=IND）
    盤後資料，快取至下次手動刷新或每日排程
    """
    data = get_cached_sectors()
    if not data:
        data = fetch_sectors()
    return {"sectors": data}


@router.get("/fear-greed")
async def get_fear_greed():
    """恐懼與貪婪指數（alternative.me，加密市場情緒），快取1小時"""
    return get_cached_fear_greed()


@router.get("/buffett")
async def get_buffett():
    """
    台股巴菲特指標：台股總市值 / GDP %
    市值來源：TWSE afterTrading 統計，fallback：TAIEX × 校正因子
    GDP：主計處年度估計值（年更新）
    快取 1 小時
    """
    return get_cached_buffett()


@router.post("/buffett/refresh")
async def refresh_buffett():
    """手動刷新巴菲特指標快取"""
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, fetch_buffett)
    return {"status": "triggered"}


@router.get("/batch-quotes")
async def get_batch_quotes(codes: str = Query(..., description="逗號分隔股票代號，如 2330,2317")):
    """
    批次取得多檔股票現價（持倉追蹤用）
    回傳：{code: {price, change_pct, name}}
    """
    from services.stock_quote_fetcher import fetch_stock_quote

    symbol_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not symbol_list or len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="codes 需為 1–50 個代號")

    async def _fetch(code: str) -> tuple[str, dict]:
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, fetch_stock_quote, code)
            return code, {"price": data.get("price", 0), "change_pct": data.get("change_pct", 0), "name": data.get("name", "")}
        except Exception:
            return code, {"price": 0, "change_pct": 0, "name": ""}

    results = await asyncio.gather(*[_fetch(c) for c in symbol_list])
    return {"quotes": dict(results)}


@router.get("/news")
async def get_market_news(limit: int = 8):
    """
    台股市場快訊：從鉅亨網抓最新新聞標題，快取 10 分鐘
    """
    from services.news_fetcher import fetch_market_news
    items = fetch_market_news(limit=limit)
    return {"items": items}


@router.get("/gov-funds")
async def get_gov_funds():
    """
    八大官股動向
    優先使用 FinMind TaiwanStockGovernmentBankBuySell，
    若無則以官股個股自營商數據作 proxy
    """
    data = get_cached_gov_funds()
    return data



@router.get("/correlation")
async def get_correlation():
    """
    台美滾動相關係數（30/60/90 日 Pearson r）
    資料來源：Yahoo Finance ^GSPC + ^TWII，每日 15:15 更新
    """
    from services.correlation_service import get_latest
    data = get_latest()
    if data:
        return data
    return {"date": None, "tw_us_corr_30d": None, "tw_us_corr_60d": None, "tw_us_corr_90d": None}



@router.get("/sector-rotation")
def get_sector_rotation():
    """產業輪動排行（composite_score = 0.5×mom4w + 0.3×mom8w + 0.2×mom13w），每週快取。"""
    import json
    from agents.sector_rotation_agent import CACHE_KEY
    from services.kv_store import kv_get
    raw = kv_get(CACHE_KEY)
    if raw:
        return json.loads(raw)
    return {"computed_at": None, "sectors": [], "message": "No data yet — run sector rotation job first"}
