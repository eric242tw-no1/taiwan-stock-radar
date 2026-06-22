"""Sector Rotation Agent — computes 4/8/13-week momentum per GICS sector and caches in Redis."""
import json
import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# TWSE industry representative ETF/index tickers mapped to GICS sector names.
# Using yfinance-compatible symbols (.TW suffix).
SECTOR_TICKERS: dict[str, list[str]] = {
    "資訊科技": ["2330.TW", "2454.TW", "2379.TW", "3661.TW"],
    "通訊服務": ["2412.TW", "4904.TW"],
    "非必需消費": ["2049.TW", "9910.TW", "2474.TW"],
    "必需消費": ["1216.TW", "1213.TW"],
    "醫療保健": ["4537.TW", "4144.TW", "1762.TW"],
    "金融": ["2881.TW", "2882.TW", "2886.TW", "2891.TW"],
    "工業": ["2317.TW", "2308.TW", "2382.TW"],
    "材料": ["2002.TW", "1301.TW", "1326.TW"],
    "能源": ["6456.TW"],
    "公用事業": ["9945.TW", "2915.TW"],
    "房地產": ["5522.TW", "2915.TW"],
}

REDIS_KEY = "sector_rotation"
REDIS_TTL = 7 * 24 * 3600  # 7 days


def _fetch_price_series(ticker: str, days: int) -> list[float]:
    """Return daily close prices for the last `days` calendar days."""
    from services.ohlcv_service import fetch_ohlcv
    rows = fetch_ohlcv(ticker, period=f"{days}d")
    return [r["close"] for r in rows if r.get("close")]


def _momentum(prices: list[float], weeks: int) -> float | None:
    """Return simple price return over `weeks` weeks (most-recent vs oldest)."""
    n = weeks * 5  # approximate trading days
    if len(prices) < n + 1:
        return None
    return (prices[-1] - prices[-(n + 1)]) / prices[-(n + 1)]


def _sector_score(tickers: list[str]) -> dict:
    """Average momentum scores across all tickers in the sector."""
    mom4w_list, mom8w_list, mom13w_list = [], [], []
    prices_needed = 14 * 5 + 5  # 14 weeks + buffer
    for ticker in tickers:
        try:
            prices = _fetch_price_series(ticker, prices_needed)
        except Exception as exc:
            logger.warning("sector_rotation: %s fetch error — %s", ticker, exc)
            continue
        m4 = _momentum(prices, 4)
        m8 = _momentum(prices, 8)
        m13 = _momentum(prices, 13)
        if m4 is not None:
            mom4w_list.append(m4)
        if m8 is not None:
            mom8w_list.append(m8)
        if m13 is not None:
            mom13w_list.append(m13)

    avg = lambda lst: sum(lst) / len(lst) if lst else 0.0
    mom4w = avg(mom4w_list)
    mom8w = avg(mom8w_list)
    mom13w = avg(mom13w_list)
    composite = 0.5 * mom4w + 0.3 * mom8w + 0.2 * mom13w
    return {"mom4w": round(mom4w, 4), "mom8w": round(mom8w, 4), "mom13w": round(mom13w, 4), "composite_score": round(composite, 4)}


def compute_sector_rotation() -> list[dict]:
    """Compute sector rotation rankings and cache to Redis. Returns sorted list."""
    results = []
    for sector, tickers in SECTOR_TICKERS.items():
        scores = _sector_score(tickers)
        results.append({"sector": sector, **scores})

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    payload = {"computed_at": str(date.today()), "sectors": results}

    try:
        import redis as redis_lib
        r = redis_lib.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload))
        logger.info("sector_rotation: cached %d sectors", len(results))
    except Exception as exc:
        logger.error("sector_rotation: Redis cache failed — %s", exc)

    return results
