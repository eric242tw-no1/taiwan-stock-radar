"""
Individual stock real-time quote from TWSE MIS.
Supports both 上市 (tse) and 上櫃 (otc) stocks.
"""
import logging
import threading
from datetime import datetime, timezone
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

# 上櫃股票代號前綴（簡單規則：5碼、6開頭、8開頭）
def _is_otc(symbol: str) -> bool:
    return len(symbol) == 5 or symbol.startswith("6") or symbol.startswith("8")

def _parse_num(s: str | None, default: float = 0.0) -> float:
    if not s or s in ("-", "--", ""):
        return default
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return default

def fetch_stock_quote(symbol: str) -> dict[str, Any]:
    """
    Fetch real-time quote for a single stock.
    symbol: 股票代號，如 "2330"（不含 .TW）
    """
    exchange = "otc" if _is_otc(symbol) else "tse"
    ex_ch = f"{exchange}_{symbol}.tw"

    try:
        with httpx.Client(headers=HEADERS, timeout=8) as client:
            resp = client.get(MIS_URL, params={"ex_ch": ex_ch, "json": "1", "delay": "0"})
            resp.raise_for_status()
            items = resp.json().get("msgArray", [])

        if not items:
            return _empty_quote(symbol)

        item = items[0]
        price      = _parse_num(item.get("z"))   # 當前價（盤中）
        prev_close = _parse_num(item.get("y"))   # 昨收
        open_      = _parse_num(item.get("o"))
        high       = _parse_num(item.get("h"))
        low        = _parse_num(item.get("l"))
        volume     = _parse_num(item.get("v"))   # 成交量（張）
        name       = item.get("n", symbol)
        update_time = item.get("t", "")

        # 盤後 z 可能為 "-"，fallback 到 u（最後成交價）或 昨收
        if price == 0:
            price = _parse_num(item.get("u"), prev_close)

        change = round(price - prev_close, 2) if price and prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0

        # 量比：today_volume / 5日均量（MIS 沒直接提供，先用昨量 b 欄估算）
        yesterday_vol = _parse_num(item.get("b"))
        vol_ratio = round(volume / yesterday_vol, 2) if yesterday_vol > 0 else None

        return {
            "symbol":      symbol,
            "name":        name,
            "exchange":    "上市" if exchange == "tse" else "上櫃",
            "price":       round(price, 2),
            "prev_close":  round(prev_close, 2),
            "open":        round(open_, 2),
            "high":        round(high, 2),
            "low":         round(low, 2),
            "change":      change,
            "change_pct":  change_pct,
            "volume":      int(volume),       # 張
            "vol_ratio":   vol_ratio,
            "update_time": update_time,
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
