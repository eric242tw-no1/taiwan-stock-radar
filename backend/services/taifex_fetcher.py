"""
TAIFEX + FX fetcher
- 大台期（TX 近月合約）from mis.taifex.com.tw
- USD/TWD from yfinance TWD=X
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import httpx
import yfinance as yf

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, Any] = {"futures": None, "fx": None, "updated_at": None}

TAIFEX_URL = "https://mis.taifex.com.tw/futures/api/getQuoteList"
TAIFEX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://mis.taifex.com.tw",
    "Referer": "https://mis.taifex.com.tw/",
}


def _parse(s: str | None, default: float = 0.0) -> float:
    if not s:
        return default
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return default


def _fetch_tx_futures() -> dict[str, Any]:
    """Fetch 大台期 near-month contract from TAIFEX MIS."""
    with httpx.Client(headers=TAIFEX_HEADERS) as client:
        resp = client.post(
            TAIFEX_URL,
            content=__import__("json").dumps(
                {"MarketType": "0", "CommodityID": "TX",
                 "RowSize": "5", "PageNo": "1", "ReqType": "I"}
            ).encode(),
            timeout=8,
        )
        resp.raise_for_status()
        items = resp.json().get("RtData", {}).get("QuoteList", [])

    # skip TXF-S (spot row), take first real futures row
    futures = [i for i in items if i.get("SymbolID", "").endswith("-F")]
    if not futures:
        raise ValueError("No TX futures row found")

    f = futures[0]
    price      = _parse(f.get("CLastPrice"))
    ref_price  = _parse(f.get("CRefPrice"))   # 昨結算價
    change     = _parse(f.get("CDiff"))
    change_pct = _parse(f.get("CDiffRate"))
    settle     = _parse(f.get("SettlementPrice"))
    name       = f.get("DispCName", "")

    # When market closed CLastPrice may be 0; fall back to SettlementPrice
    if price == 0 and settle > 0:
        price = settle

    return {
        "price":      round(price, 0),
        "ref_price":  round(ref_price, 0),
        "change":     round(change, 0),
        "change_pct": round(change_pct, 2),
        "name":       name,
        "symbol":     f.get("SymbolID", ""),
    }


def _fetch_usdtwd() -> dict[str, Any]:
    """Fetch USD/TWD from yfinance TWD=X."""
    t = yf.Ticker("TWD=X")
    info = t.fast_info
    price      = float(info.last_price or 0)
    prev_close = float(info.previous_close or price)
    change_pct = round((price - prev_close) / prev_close * 100, 3) if prev_close else 0.0
    return {
        "price":      round(price, 3),
        "change_pct": change_pct,
    }


def fetch_futures_and_fx() -> dict[str, Any]:
    """Fetch both TX futures and USD/TWD; update cache."""
    result: dict[str, Any] = {}

    try:
        result["futures"] = _fetch_tx_futures()
    except Exception as exc:
        logger.warning("TX futures fetch failed: %s", exc)
        result["futures"] = (_cache.get("futures") or {
            "price": 0, "ref_price": 0, "change": 0, "change_pct": 0,
            "name": "大台期", "symbol": "",
        })

    try:
        result["fx"] = _fetch_usdtwd()
    except Exception as exc:
        logger.warning("USD/TWD fetch failed: %s", exc)
        result["fx"] = (_cache.get("fx") or {"price": 0, "change_pct": 0})

    with _lock:
        _cache["futures"]    = result["futures"]
        _cache["fx"]         = result["fx"]
        _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("futures=%s  fx=%s", result["futures"]["price"], result["fx"]["price"])
    return result


def get_cached_futures_and_fx() -> dict[str, Any]:
    with _lock:
        f, fx = _cache.get("futures"), _cache.get("fx")
    if f is None or fx is None:
        return fetch_futures_and_fx()
    return {"futures": f, "fx": fx}


def get_futures_cache_meta() -> dict[str, Any]:
    with _lock:
        return {"updated_at": _cache.get("updated_at")}
