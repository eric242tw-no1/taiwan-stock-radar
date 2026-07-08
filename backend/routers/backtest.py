"""
回測 API
POST /api/backtest
Body:
{
  "symbol": "2330",
  "start": "2023-01-01",
  "end": "2024-12-31",
  "strategy": "wave",          // wave | momentum
  "initial_cash": 1000000,
  "params": {
    "stop_loss_pct": 0.07,
    "take_profit_pct": 0.15,
    "max_hold_days": 20
  }
}
"""
import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from backtest.engine import fetch_backtest_data, run_backtest

router = APIRouter(tags=["backtest"])

# in-memory result store {result_id: {"status": "running"|"done"|"error", "result": dict}}
_results: dict[str, dict] = {}


class BacktestRequest(BaseModel):
    symbol:       str
    start:        str = Field(..., example="2023-01-01")
    end:          str = Field(..., example="2024-12-31")
    strategy:     str = Field("wave", description="wave | momentum")
    initial_cash: float = 1_000_000
    params:       dict = {}


async def _run_backtest_task(result_id: str, body: BacktestRequest) -> None:
    try:
        df = await fetch_backtest_data(body.symbol, body.start, body.end)
        result = await asyncio.to_thread(run_backtest, df, body.strategy, body.params, body.initial_cash)
        _results[result_id] = {
            "status": "done",
            "result": {"symbol": body.symbol, "start": body.start, "end": body.end, "bars": len(df), **result},
        }
    except Exception as e:
        _results[result_id] = {"status": "error", "error": str(e)}


@router.get("/api/backtest/{result_id}")
def get_result(result_id: str):
    """查詢回測結果（status: running | done | error）。"""
    item = _results.get(result_id)
    if not item:
        raise HTTPException(status_code=404, detail="Result not found")
    return item


@router.post("/api/backtest")
async def run(body: BacktestRequest):
    try:
        df = await fetch_backtest_data(body.symbol, body.start, body.end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"資料取得失敗：{e}")

    if len(df) < 60:
        raise HTTPException(status_code=422, detail="資料不足 60 筆，無法回測")

    try:
        result = await asyncio.to_thread(
            run_backtest, df, body.strategy, body.params, body.initial_cash
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回測執行失敗：{e}")

    return {
        "symbol":  body.symbol,
        "start":   body.start,
        "end":     body.end,
        "bars":    len(df),
        **result,
    }


@router.get("/api/backtest/strategies")
def list_strategies():
    return {
        "strategies": [
            {
                "id": "wave",
                "name": "波段技術分析",
                "desc": "MACD 黃金交叉 + RSI < 70 + 站上 MA20",
                "params": {"stop_loss_pct": 0.07, "take_profit_pct": 0.15, "max_hold_days": 20},
            },
            {
                "id": "momentum",
                "name": "趨勢跟隨",
                "desc": "創 60 日新高 + 連 3 日收紅",
                "params": {"stop_loss_pct": 0.10, "max_hold_days": 42},
            },
            {
                "id": "ma_cross",
                "name": "MA 黃金交叉",
                "desc": "短均穿越長均買入，死叉賣出",
                "params": {"short_period": 10, "long_period": 30, "stop_loss_pct": 0.08},
            },
            {
                "id": "rsi",
                "name": "RSI 超買超賣",
                "desc": "RSI 從超賣回升買入，從超買回落賣出",
                "params": {"rsi_period": 14, "oversold": 30, "overbought": 70, "stop_loss_pct": 0.08},
            },
        ]
    }
