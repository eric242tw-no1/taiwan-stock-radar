"""
Individual stock real-time quote from TWSE MIS.
Supports both 上市 (tse) and 上櫃 (otc) stocks.
"""
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mis.twse.com.tw/",
}


def _parse_num(s: str | None, default: float = 0.0) -> float:
    if not s or s in ("-", "--", ""):
        return default
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return default


def _query_exchange(symbol: str, exchange: str, client: httpx.Client) -> dict | None:
    """Query MIS for one exchange; return raw item dict or None if no valid data."""
    resp = client.get(MIS_URL, params={"ex_ch": f"{exchange}_{symbol}.tw", "json": "1", "delay": "0"})
    resp.raise_for_status()
    items = resp.json().get("msgArray", [])
    if not items:
        return None
    item = items[0]
    # MIS returns a placeholder record for wrong-exchange queries with no real name
    name = item.get("n", "")
    if not name or name == symbol:
        return None
    return item


def fetch_stock_quote(symbol: str) -> dict[str, Any]:
    """
    Fetch real-time quote for a single stock.
    Tries TSE first, then OTC as fallback (handles ambiguous 6xxx/8xxx codes).
    symbol: 股票代號，如 "2330"（不含 .TW）
    """
    try:
        with httpx.Client(headers=HEADERS, timeout=8) as client:
            item, exchange = None, "tse"
            for ex in ("tse", "otc"):
                item = _query_exchange(symbol, ex, client)
                if item is not None:
                    exchange = ex
                    break

        if item is None:
            return _empty_quote(symbol)

        price      = _parse_num(item.get("z"))
        prev_close = _parse_num(item.get("y"))
        open_      = _parse_num(item.get("o"))
        high       = _parse_num(item.get("h"))
        low        = _parse_num(item.get("l"))
        volume     = _parse_num(item.get("v"))
        name       = item.get("n", symbol)
        update_time = item.get("t", "")

        # 盤後 z 可能為 "-"，fallback 到 u（最後成交價）或昨收
        if price == 0:
            price = _parse_num(item.get("u"), prev_close)

        change = round(price - prev_close, 2) if price and prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        yesterday_vol = _parse_num(item.get("b"))
        vol_ratio = round(volume / yesterday_vol, 2) if yesterday_vol > 0 else None

        return {
            "symbol":        symbol,
            "name":          name,
            "exchange":      "上市" if exchange == "tse" else "上櫃",
            "price":         round(price, 2),
            "prev_close":    round(prev_close, 2),
            "open":          round(open_, 2),
            "high":          round(high, 2),
            "low":           round(low, 2),
            "change":        change,
            "change_pct":    change_pct,
            "volume":        int(volume),
            "vol_ratio":     vol_ratio,
            "update_time":   update_time,
            "market_status": _market_status(),
        }
    except Exception as e:
        logger.error("stock_quote fetch failed [%s]: %s", symbol, e)
        return _empty_quote(symbol)


def _market_status() -> str:
    now = datetime.now()
    if now.weekday() >= 5:
        return "休市"
    h, m = now.hour, now.minute
    if (h, m) < (9, 0):
        return "盤前"
    if (h, m) <= (13, 30):
        return "盤中"
    return "盤後"


def _empty_quote(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol, "name": symbol, "exchange": "上市",
        "price": 0, "prev_close": 0, "open": 0, "high": 0, "low": 0,
        "change": 0, "change_pct": 0, "volume": 0,
        "vol_ratio": None, "update_time": "", "market_status": "未知",
    }
