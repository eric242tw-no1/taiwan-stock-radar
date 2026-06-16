"""Strategy Analytics API — reads from backtest_results."""
import json
import logging
import math
from typing import Optional

from fastapi import APIRouter, Query

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()


def _sharpe(total_return: float, max_drawdown: float, win_rate: float) -> float:
    if max_drawdown == 0:
        return 0.0
    volatility_proxy = abs(max_drawdown) / math.sqrt(252) * 10
    excess_return = total_return - 0.02
    return round(excess_return / volatility_proxy, 4) if volatility_proxy > 0 else 0.0


@router.get("/strategies")
def get_strategy_analytics(
    symbol: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    conn = get_conn()
    cur = conn.cursor()
    if symbol:
        cur.execute(
            "SELECT id, symbol, period_start, period_end, win_rate, total_return, max_drawdown, trades, created_at "
            "FROM backtest_results WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol, limit),
        )
    else:
        cur.execute(
            "SELECT id, symbol, period_start, period_end, win_rate, total_return, max_drawdown, trades, created_at "
            "FROM backtest_results ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        win_rate = float(r[4] or 0)
        total_return = float(r[5] or 0)
        max_drawdown = float(r[6] or 0)
        trades_raw = r[7] or "[]"
        trades = json.loads(trades_raw) if isinstance(trades_raw, str) else (trades_raw or [])

        equity_curve = []
        cumulative = 1.0
        if isinstance(trades, list):
            for t in trades:
                pnl = t.get("pnl", 0) if isinstance(t, dict) else 0
                cumulative *= (1 + pnl / 100)
                equity_curve.append(round(cumulative, 4))

        results.append({
            "id": r[0],
            "symbol": r[1],
            "period_start": str(r[2]) if r[2] else None,
            "period_end": str(r[3]) if r[3] else None,
            "win_rate": win_rate,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": _sharpe(total_return, max_drawdown, win_rate),
            "trade_count": len(trades) if isinstance(trades, list) else 0,
            "equity_curve": equity_curve,
            "created_at": str(r[8]),
        })

    return {"strategies": results}
