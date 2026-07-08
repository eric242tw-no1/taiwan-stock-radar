import json
import logging
import os

from fastapi import APIRouter, Query

from db import get_conn
from services.risk_manager import RiskDecision, RiskManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk", tags=["risk"])

_rm = RiskManager()
_ATR_CACHE_TTL = 300  # seconds


def _get_redis():
    host = os.getenv("REDIS_HOST", "")
    if not host:
        raise RuntimeError("REDIS_HOST not set — ATR cache disabled")
    import redis
    return redis.Redis(
        host=host,
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )


@router.get("/atr-stop/{symbol}")
async def get_atr_stop(
    symbol: str,
    multiplier: float = Query(2.0, description="ATR 倍數（停損距離 = ATR × multiplier）"),
    entry_price: float = Query(None, description="進場價（省略則用最新收盤價）"),
):
    cache_key = f"atr_stop:{symbol}:{multiplier}"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached and entry_price is None:
            return json.loads(cached)
    except Exception:
        pass

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT close, high, low FROM daily_price WHERE symbol=? ORDER BY date DESC LIMIT 20",
            (symbol,),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"DB 讀取失敗: {exc}")

    if len(rows) < 15:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 歷史資料不足")

    import pandas as pd
    df = pd.DataFrame(rows, columns=["close", "high", "low"])
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(-1)).abs()
    low_close = (df["low"] - df["close"].shift(-1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr_14 = float(tr.head(14).mean())

    ref_price = entry_price if entry_price else float(df["close"].iloc[0])
    stop_loss = round(ref_price - atr_14 * multiplier, 2)
    stop_pct = round((ref_price - stop_loss) / ref_price * 100, 2)

    result = {
        "symbol": symbol, "atr_14": round(atr_14, 4),
        "multiplier": multiplier, "ref_price": ref_price,
        "stop_loss": stop_loss, "stop_pct": stop_pct,
    }

    try:
        r = _get_redis()
        r.setex(cache_key, _ATR_CACHE_TTL, json.dumps(result))
    except Exception:
        pass

    return result


@router.get("/watching")
async def get_watching():
    from scheduler_tasks import stop_loss_guard
    return {"watching": stop_loss_guard.watching}


@router.get("/assessment/{symbol}")
async def get_risk_assessment(
    symbol: str,
    size: int = Query(1000, description="計劃交易股數"),
    capital: float = Query(1_000_000, description="總資金（元）"),
    portfolio: str = Query("", description="逗號分隔的已持倉股票代號"),
):
    held = [s.strip() for s in portfolio.split(",") if s.strip()]

    checks = {
        "position_size":    _rm.check_position_size(symbol, size, capital),
        "max_drawdown":     _rm.check_max_drawdown(),
        "correlation_risk": _rm.check_correlation_risk(symbol, held),
    }

    overall_approved = all(d.approved for d in checks.values())
    failed = [name for name, d in checks.items() if not d.approved]

    return {
        "symbol":           symbol,
        "overall_approved": overall_approved,
        "failed_checks":    failed,
        "checks": {
            name: {"approved": d.approved, "reason": d.reason, "detail": d.detail}
            for name, d in checks.items()
        },
    }
