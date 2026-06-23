"""
選股掃描 API
GET /api/screener?strategy=ma20_breakout&min_volume_lot=500&min_change_pct=2

strategy 選項：
  ma20_breakout   突破 MA20 + 帶量
  rsi_oversold    RSI(14) 超賣反彈
  high_60d        創近 60 日新高
  (空白)          純基礎篩選

快取：同一組參數 5 分鐘內回傳快取結果
"""
import hashlib
import json
import time
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from agents.screener_agent import fetch_market_snapshot, apply_basic_filters, apply_tech_filters

router = APIRouter(tags=["screener"])

_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 300  # 5 分鐘

# 因子掃描股票池產業對照（純展示用，無真實產業資料庫時的靜態對照）
_INDUSTRY_MAP = {
    "0050": "ETF", "2330": "半導體", "2317": "電子製造", "2454": "半導體",
    "2308": "電子零組件", "2382": "電子製造", "2412": "電信", "2881": "金融",
    "2303": "半導體", "2002": "鋼鐵", "1301": "石化", "3008": "光電",
    "2886": "金融", "2891": "金融", "2603": "航運", "3711": "半導體",
    "2379": "半導體", "6669": "伺服器", "4968": "半導體", "3034": "半導體",
}


async def _apply_indicator_filters(
    stocks: list[dict],
    patterns: list[str],
    phase: Optional[str],
) -> list[dict]:
    """呼叫 indicators API 過濾 K 線形態 / 主力意圖（並行批次）。"""
    import asyncio
    import httpx

    if not patterns and not phase:
        return stocks

    async def fetch_ind(client: httpx.AsyncClient, symbol: str) -> dict:
        try:
            r = await client.get(f"http://localhost:8000/api/market/indicators/{symbol}.TW", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    async with httpx.AsyncClient() as client:
        tasks = [fetch_ind(client, s["symbol"]) for s in stocks]
        inds = await asyncio.gather(*tasks)

    result = []
    for stock, ind in zip(stocks, inds):
        if patterns:
            stock_patterns = ind.get("patterns", [])
            if not any(p in stock_patterns for p in patterns):
                continue
        if phase:
            mmi = ind.get("market_maker_intent", {})
            if mmi.get("phase") != phase:
                continue
        result.append(stock)
    return result


@router.get("/api/screener")
async def screen_stocks(
    strategy: Optional[str] = Query(None, description="ma20_breakout | rsi_oversold | high_60d"),
    min_change_pct: Optional[float] = Query(None, description="漲幅下限 %"),
    max_change_pct: Optional[float] = Query(None, description="漲幅上限 %"),
    min_volume_lot: Optional[int] = Query(500, description="成交量下限（張）"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    patterns: Optional[str] = Query(None, description="K線形態，逗號分隔，如 多頭吞噬,晨星"),
    phase: Optional[str] = Query(None, description="主力意圖階段：吸籌|拉抬|出貨|打壓|觀望"),
    limit: int = Query(50, le=200),
):
    criteria = {
        "min_change_pct": min_change_pct,
        "max_change_pct": max_change_pct,
        "min_volume_lot": min_volume_lot,
        "min_price": min_price,
        "max_price": max_price,
    }
    pattern_list = [p.strip() for p in patterns.split(",")] if patterns else []
    cache_key = hashlib.md5(
        json.dumps({"strategy": strategy, "patterns": pattern_list, "phase": phase, **criteria}, sort_keys=True).encode()
    ).hexdigest()

    if cache_key in _cache:
        ts, result = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return {"source": "cache", "count": len(result), "stocks": result[:limit]}

    df = await fetch_market_snapshot()
    df = apply_basic_filters(df, {k: v for k, v in criteria.items() if v is not None})

    if strategy:
        df = await apply_tech_filters(df, strategy)

    df = df.sort_values("volume_lot", ascending=False)
    result = df[["symbol", "name", "close", "change", "change_pct", "volume_lot"]].to_dict("records")

    if pattern_list or phase:
        result = await _apply_indicator_filters(result, pattern_list, phase)

    _cache[cache_key] = (time.time(), result)

    return {"source": "live", "count": len(result), "stocks": result[:limit]}


class ScreenerRunRequest(BaseModel):
    strategy: Optional[str] = None
    min_change_pct: Optional[float] = None
    max_change_pct: Optional[float] = None
    min_volume_lot: Optional[int] = 500
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort_by: str = "volume_lot"
    limit: int = 50


@router.post("/api/screener/run")
async def run_screener_sync(body: ScreenerRunRequest):
    """Run screener synchronously (no Celery required)."""
    criteria = {
        "min_change_pct": body.min_change_pct,
        "max_change_pct": body.max_change_pct,
        "min_volume_lot": body.min_volume_lot,
        "min_price": body.min_price,
        "max_price": body.max_price,
    }
    cache_key = hashlib.md5(
        json.dumps({"strategy": body.strategy, **criteria}, sort_keys=True).encode()
    ).hexdigest()

    if cache_key in _cache:
        ts, result = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return {"source": "cache", "count": len(result), "stocks": result[:body.limit]}

    df = await fetch_market_snapshot()
    df = apply_basic_filters(df, {k: v for k, v in criteria.items() if v is not None})

    if body.strategy:
        df = await apply_tech_filters(df, body.strategy)

    df = df.sort_values(body.sort_by if body.sort_by in df.columns else "volume_lot", ascending=False)

    result = df[["symbol", "name", "close", "change", "change_pct", "volume_lot"]].to_dict("records")
    _cache[cache_key] = (time.time(), result)

    return {"source": "live", "count": len(result), "stocks": result[:body.limit]}


@router.get("/api/screener/factor-scan")
async def factor_scan(limit: int = Query(50, le=100)):
    """
    因子掃描：股票池 + 真實股價/RSI/均線/籌碼/AI 評分。
    價/漲跌/量來自 TWSE 即時；RSI/均線來自 stock_indicators_daily；
    外資來自 chip_data；AI 評分來自 Redis 快取。無資料的欄位回 null。
    """
    from services.stock_pool_service import get_pool
    from agents.ai_engine import _cache_get, _cache_key
    from db import get_conn

    pool = get_pool()
    if not pool:
        return {"source": "live", "count": 0, "stocks": []}

    # 真實股價（TWSE 全市場一次，過濾股票池）
    try:
        snap = await fetch_market_snapshot()
        snap_map = {row["symbol"]: row for row in snap.to_dict("records")}
    except Exception:
        snap_map = {}

    conn = get_conn()
    cards = []
    try:
        for p in pool:
            sym = p["symbol"]
            s = snap_map.get(sym, {})

            ind = conn.execute(
                "SELECT close, rsi14, ma20, ma20_bias FROM stock_indicators_daily "
                "WHERE ticker=? ORDER BY trade_date DESC LIMIT 1",
                (f"{sym}.TW",),
            ).fetchone()
            chip = conn.execute(
                "SELECT foreign_buy FROM chip_data WHERE symbol=? ORDER BY date DESC LIMIT 1",
                (sym,),
            ).fetchone()

            ai_raw = await _cache_get(_cache_key(sym))
            ai_score = None
            if ai_raw:
                try:
                    ai_score = json.loads(ai_raw).get("score")
                except Exception:
                    pass

            close = s.get("close") or (ind["close"] if ind else None)
            change_pct = s.get("change_pct")
            volume_lot = s.get("volume_lot")
            rsi = ind["rsi14"] if ind else None
            ma20 = ind["ma20"] if ind else None
            ma_align = (close > ma20) if (close and ma20) else None
            foreign_buy = (
                chip["foreign_buy"] > 0
                if chip and chip["foreign_buy"] is not None else None
            )
            volume_bn = (
                round(close * volume_lot * 1000 / 1e8, 1)
                if (close and volume_lot) else None
            )

            cards.append({
                "code": sym,
                "name": p["name"],
                "price": round(close, 2) if close else None,
                "change_pct": change_pct,
                "volume_bn": volume_bn,
                "vol_ratio": None,
                "rsi": round(rsi, 1) if rsi is not None else None,
                "ma_align": ma_align,
                "foreign_buy": foreign_buy,
                "ai_score": ai_score,
                "industry": _INDUSTRY_MAP.get(sym, ""),
                "limit_up": (change_pct is not None and change_pct >= 9.5),
                "limit_down": (change_pct is not None and change_pct <= -9.5),
                "big_order_in": None,
                "gap_up": None,
            })
    finally:
        conn.close()

    cards.sort(key=lambda c: (c["ai_score"] or 0, c["volume_bn"] or 0), reverse=True)
    return {"source": "live", "count": len(cards), "stocks": cards[:limit]}
