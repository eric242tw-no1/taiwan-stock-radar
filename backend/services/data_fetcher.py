"""
Data fetcher service — yfinance US indices + VIX
Updates in-memory cache every 5 minutes (盤中) via APScheduler.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# In-memory cache (thread-safe with a lock)
# --------------------------------------------------------------------------- #
_lock = threading.Lock()
_cache: dict[str, Any] = {
    "us_indices": None,
    "updated_at": None,
}

SYMBOLS = {
    "sp500":  "^GSPC",
    "nasdaq": "^IXIC",
    "dji":    "^DJI",
    "vix":    "^VIX",
}


def _vix_meta(price: float) -> dict[str, str]:
    if price < 20:
        return {"level": "low",    "label": "低恐慌", "color": "green"}
    if price < 30:
        return {"level": "medium", "label": "中恐慌", "color": "yellow"}
    return     {"level": "high",   "label": "高恐慌", "color": "red"}


def fetch_us_indices() -> dict[str, Any]:
    """
    Pull latest quote for all four symbols in one yfinance batch call.
    Returns the structured dict expected by /api/market/us-indices.
    Falls back to last cached value on error.
    """
    tickers = yf.Tickers(" ".join(SYMBOLS.values()))

    result: dict[str, Any] = {}
    for key, symbol in SYMBOLS.items():
        try:
            info = tickers.tickers[symbol].fast_info
            price      = float(info.last_price or 0)
            prev_close = float(info.previous_close or price)
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

            entry: dict[str, Any] = {
                "price":      round(price, 2),
                "change_pct": change_pct,
            }
            if key == "vix":
                entry.update(_vix_meta(price))

            result[key] = entry
        except Exception as exc:
            logger.warning("yfinance error for %s: %s", symbol, exc)
            # keep whatever was cached for this key
            cached = (_cache.get("us_indices") or {}).get(key)
            result[key] = cached or {
                "price": 0, "change_pct": 0,
                **({"level": "low", "label": "低恐慌", "color": "green"} if key == "vix" else {}),
            }

    with _lock:
        _cache["us_indices"] = result
        _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("us_indices refreshed at %s", _cache["updated_at"])
    return result


def get_cached_us_indices() -> dict[str, Any]:
    """Return cached data; fetch fresh if cache is empty."""
    with _lock:
        data = _cache.get("us_indices")
    if data is None:
        return fetch_us_indices()
    return data


def get_cache_meta() -> dict[str, Any]:
    with _lock:
        return {"updated_at": _cache.get("updated_at")}
