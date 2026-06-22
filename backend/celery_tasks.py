"""Celery task definitions — loaded by celery_app via include=["celery_tasks"]."""
import asyncio

from celery import shared_task


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


@shared_task(name="score_symbol")
def score_symbol(symbol: str) -> dict:
    from agents.ai_engine import get_ai_analysis
    return _run_async(get_ai_analysis(symbol, force=True))


@shared_task(name="run_screener")
def run_screener(params: dict | None = None) -> dict:
    from agents.screener_agent import fetch_market_snapshot, apply_basic_filters, apply_tech_filters

    params = params or {}

    async def _inner():
        df = await fetch_market_snapshot()
        criteria = {k: v for k, v in params.items() if k in (
            "min_change_pct", "max_change_pct", "min_volume_lot", "min_price", "max_price"
        ) and v is not None}
        df = apply_basic_filters(df, criteria)
        strategy = params.get("strategy")
        if strategy:
            df = await apply_tech_filters(df, strategy)
        limit = params.get("limit", 50)
        sort_by = params.get("sort_by", "volume_lot")
        valid_sort = sort_by if sort_by in df.columns else "volume_lot"
        df = df.sort_values(valid_sort, ascending=False)
        records = df[["symbol", "name", "close", "change", "change_pct", "volume_lot"]].to_dict("records")
        return {"count": len(records), "stocks": records[:limit]}

    return _run_async(_inner())


@shared_task(name="run_backtest")
def run_backtest(params: dict) -> dict:
    from backtest.engine import fetch_backtest_data, run_backtest as _run_backtest

    async def _inner():
        symbol = params["symbol"]
        start = params["start"]
        end = params["end"]
        strategy = params.get("strategy", "wave")
        initial_cash = params.get("initial_cash", 1_000_000)
        extra_params = params.get("params", {})
        df = await fetch_backtest_data(symbol, start, end)
        result = await asyncio.to_thread(_run_backtest, df, strategy, extra_params, initial_cash)
        return {"symbol": symbol, "start": start, "end": end, "bars": len(df), **result}

    return _run_async(_inner())
