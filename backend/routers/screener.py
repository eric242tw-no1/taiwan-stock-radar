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


@router.get("/api/screener")
async def screen_stocks(
    strategy: Optional[str] = Query(None, description="ma20_breakout | rsi_oversold | high_60d"),
    min_change_pct: Optional[float] = Query(None, description="漲幅下限 %"),
    max_change_pct: Optional[float] = Query(None, description="漲幅上限 %"),
    min_volume_lot: Optional[int] = Query(500, description="成交量下限（張）"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    limit: int = Query(50, le=200),
):
    criteria = {
        "min_change_pct": min_change_pct,
        "max_change_pct": max_change_pct,
        "min_volume_lot": min_volume_lot,
        "min_price": min_price,
        "max_price": max_price,
    }
    cache_key = hashlib.md5(
        json.dumps({"strategy": strategy, **criteria}, sort_keys=True).encode()
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
async def run_screener(body: ScreenerRunRequest):
    """POST 版選股掃描，支援動能因子（momentum_20d）、籌碼因子（foreign_consec）。"""
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

    valid_sort = body.sort_by if body.sort_by in df.columns else "volume_lot"
    df = df.sort_values(valid_sort, ascending=False)

    result = df[["symbol", "name", "close", "change", "change_pct", "volume_lot"]].to_dict("records")
    _cache[cache_key] = (time.time(), result)

    return {"source": "live", "count": len(result), "stocks": result[:body.limit]}
