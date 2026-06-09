"""
FinMind 三大法人買賣超
- 市場總覽：抓主要權值股（2330/2317/2454/2412）合計外資/投信/自營方向
- 個股籌碼：供 /api/stock/{id}/chip 使用
- 免費 600次/hr，收盤後14:30更新一次即可
"""
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

_lock = threading.Lock()
_cache: dict[str, Any] = {"chip": None, "updated_at": None}

# 代表性權值股：台積電/鴻海/聯發科/中華電
REPR_STOCKS = ["2330", "2317", "2454", "2412"]

NAME_MAP = {
    "Foreign_Investor":    "foreign",
    "Foreign_Dealer_Self": "foreign",   # 外資自營併入外資
    "Investment_Trust":    "trust",
    "Dealer_self":         "dealer",
    "Dealer_Hedging":      "dealer",    # 自營避險併入自營
}


def _get_token() -> str:
    token = os.environ.get("FINMIND_TOKEN", "")
    if not token or token == "placeholder":
        raise ValueError("FINMIND_TOKEN not configured")
    return token


def _fetch_institutional(stock_id: str, start_date: str, client: httpx.Client) -> list[dict]:
    resp = client.get(
        FINMIND_URL,
        params={
            "dataset":    "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id":    stock_id,
            "start_date": start_date,
            "token":      _get_token(),
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 200:
        raise ValueError(f"FinMind error: {data.get('msg')}")
    return data.get("data", [])


def _aggregate(rows: list[dict]) -> dict[str, int]:
    """Sum buy-sell net for each investor type on the latest date."""
    if not rows:
        return {"foreign": 0, "trust": 0, "dealer": 0, "date": ""}

    latest_date = max(r["date"] for r in rows)
    net: dict[str, int] = {"foreign": 0, "trust": 0, "dealer": 0}
    for r in rows:
        if r["date"] != latest_date:
            continue
        key = NAME_MAP.get(r["name"])
        if key:
            net[key] += int(r["buy"]) - int(r["sell"])
    net["date"] = latest_date
    return net


def fetch_chip_summary() -> dict[str, Any]:
    """
    Fetch 三大法人 net buy/sell for representative stocks.
    Returns aggregated direction per investor type + per-stock detail.
    """
    token_ok = True
    try:
        _get_token()
    except ValueError:
        token_ok = False

    if not token_ok:
        result = _empty_chip()
        result["error"] = "FINMIND_TOKEN not configured"
        return result

    start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    per_stock: dict[str, dict] = {}
    totals: dict[str, int] = {"foreign": 0, "trust": 0, "dealer": 0}

    with httpx.Client() as client:
        for sid in REPR_STOCKS:
            try:
                rows = _fetch_institutional(sid, start_date, client)
                agg = _aggregate(rows)
                per_stock[sid] = agg
                for k in ["foreign", "trust", "dealer"]:
                    totals[k] += agg.get(k, 0)
            except Exception as exc:
                logger.warning("FinMind fetch failed [%s]: %s", sid, exc)
                per_stock[sid] = {"foreign": 0, "trust": 0, "dealer": 0, "date": ""}

    result = {
        "totals": totals,
        "per_stock": per_stock,
        "repr_stocks": REPR_STOCKS,
    }

    with _lock:
        _cache["chip"] = result
        _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("chip_summary refreshed — foreign net: %d", totals["foreign"])
    return result


def _empty_chip() -> dict[str, Any]:
    return {
        "totals":      {"foreign": 0, "trust": 0, "dealer": 0},
        "per_stock":   {},
        "repr_stocks": REPR_STOCKS,
    }


def get_cached_chip() -> dict[str, Any]:
    with _lock:
        data = _cache.get("chip")
    return data if data is not None else fetch_chip_summary()


def get_chip_cache_meta() -> dict[str, Any]:
    with _lock:
        return {"updated_at": _cache.get("updated_at")}


def fetch_stock_chip(stock_id: str) -> dict[str, Any]:
    """Fetch chip data for a single stock (used by individual stock page)."""
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        with httpx.Client() as client:
            rows = _fetch_institutional(stock_id, start_date, client)
        return {"stock_id": stock_id, "data": rows, "latest": _aggregate(rows)}
    except Exception as exc:
        logger.warning("fetch_stock_chip [%s]: %s", stock_id, exc)
        return {"stock_id": stock_id, "data": [], "latest": _empty_chip()["totals"], "error": str(exc)}


def fetch_margin(stock_id: str) -> dict[str, Any]:
    """
    Fetch 融資融券 for a single stock via FinMind TaiwanStockMarginPurchaseShortSale.
    Returns latest balance + 5-day change.
    """
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        with httpx.Client() as client:
            resp = client.get(
                FINMIND_URL,
                params={
                    "dataset":    "TaiwanStockMarginPurchaseShortSale",
                    "data_id":    stock_id,
                    "start_date": start_date,
                    "token":      _get_token(),
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        rows = data.get("data", [])
        if not rows:
            return _empty_margin()

        # 取最後兩筆計算變化
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        latest = rows_sorted[-1]
        prev   = rows_sorted[-2] if len(rows_sorted) >= 2 else latest

        margin_today = int(latest.get("MarginPurchaseTodayBalance", 0))
        margin_prev  = int(prev.get("MarginPurchaseTodayBalance", 0))
        short_today  = int(latest.get("ShortSaleTodayBalance", 0))
        short_prev   = int(prev.get("ShortSaleTodayBalance", 0))

        # 券資比
        ratio = round(short_today / margin_today * 100, 2) if margin_today > 0 else 0

        return {
            "date":          latest["date"],
            "margin_balance": margin_today,         # 融資餘額（張）
            "margin_change":  margin_today - margin_prev,
            "short_balance":  short_today,          # 融券餘額（張）
            "short_change":   short_today - short_prev,
            "short_ratio":    ratio,                # 券資比 %
        }
    except Exception as exc:
        logger.warning("fetch_margin [%s]: %s", stock_id, exc)
        return _empty_margin()


def _empty_margin() -> dict[str, Any]:
    return {
        "date": "", "margin_balance": 0, "margin_change": 0,
        "short_balance": 0, "short_change": 0, "short_ratio": 0,
    }
