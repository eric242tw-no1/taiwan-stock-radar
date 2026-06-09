"""
OHLCV service: fetch historical candlestick data from yfinance.
Cached in-memory per ticker+period to avoid hammering yfinance.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, dict] = {}  # key: "ticker:period"


def _cache_key(ticker: str, period: str) -> str:
    return f"{ticker}:{period}"


def fetch_ohlcv(ticker: str, period: str = "90d") -> list[dict[str, Any]]:
    key = _cache_key(ticker, period)
    now = datetime.now(timezone.utc)

    with _lock:
        cached = _cache.get(key)
        if cached:
            age_sec = (now - cached["fetched_at"]).total_seconds()
            if age_sec < 3600:  # 1 hour cache
                return cached["bars"]

    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []

        # Handle MultiIndex columns from newer yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]

        bars = []
        for ts, row in df.iterrows():
            date_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            bars.append({
                "time":   date_str,
                "open":   round(float(row["open"]),  2),
                "high":   round(float(row["high"]),  2),
                "low":    round(float(row["low"]),   2),
                "close":  round(float(row["close"]), 2),
                "volume": int(row["volume"]) if not pd.isna(row["volume"]) else 0,
            })

        with _lock:
            _cache[key] = {"bars": bars, "fetched_at": now}

        return bars
    except Exception as e:
        logger.error("ohlcv fetch failed [%s %s]: %s", ticker, period, e)
        return []
