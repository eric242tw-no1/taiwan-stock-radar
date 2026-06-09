"""
TWSE MIS 即時資料抓取
- 加權指數 (tse_t00.tw)
- OTC 櫃買指數 (otc_o00.tw)
- 大台期（近月期貨，TAIFEX 另外接）
- 漲跌家數：TWSE afterTrading MI_INDEX table[7]
- 成交金額：MI_INDEX table[6]

MIS 限制：5秒內最多3次請求
afterTrading API：每日14:30收盤後才有當日完整資料
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, Any] = {
    "tw_market": None,
    "updated_at": None,
}

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
# 盤中即時漲跌家數（TWSE 統計頁，每分鐘更新）
MI_INDEX5_URL = "https://www.twse.com.tw/rwd/zh/fund/MI_INDEX5"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mis.twse.com.tw/",
}


def _parse_num(s: str | None, default: float = 0.0) -> float:
    if not s or s == "-":
        return default
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return default


def _change_pct(price: float, prev_close: float) -> float:
    if prev_close == 0:
        return 0.0
    return round((price - prev_close) / prev_close * 100, 2)


def _fetch_mis_index(ex_ch: str, client: httpx.Client) -> dict[str, Any]:
    """Fetch a single index from TWSE MIS."""
    resp = client.get(
        MIS_URL,
        params={"ex_ch": ex_ch, "json": "1", "delay": "0"},
        timeout=8,
    )
    resp.raise_for_status()
    items = resp.json().get("msgArray", [])
    if not items:
        raise ValueError(f"Empty msgArray for {ex_ch}")
    item = items[0]
    price      = _parse_num(item.get("z"))
    prev_close = _parse_num(item.get("y"))
    open_      = _parse_num(item.get("o"))
    high       = _parse_num(item.get("h"))
    low        = _parse_num(item.get("l"))
    # m = 成交金額（萬元）
    trade_val  = _parse_num(item.get("m"))
    update_time = item.get("t", "")

    return {
        "price":      round(price, 2),
        "prev_close": round(prev_close, 2),
        "open":       round(open_, 2),
        "high":       round(high, 2),
        "low":        round(low, 2),
        "change":     round(price - prev_close, 2),
        "change_pct": _change_pct(price, prev_close),
        "trade_value_bn": round(trade_val / 100_000, 2),  # 億元
        "update_time": update_time,
    }


def _parse_breadth_count(s: str) -> int:
    """'3,144(43)' → 3144  |  '253' → 253"""
    return int(s.split("(")[0].replace(",", ""))


def _fetch_intraday_breadth(client: httpx.Client) -> dict[str, Any] | None:
    """
    盤中漲跌家數：TWSE MI_INDEX5（每分鐘更新，盤中才有資料）
    欄位順序：[日期, 上漲, 限漲, 下跌, 限跌, 持平, 未成交, 無比較]
    回傳 None 表示資料不可用（盤中但尚未開盤，或非交易日）
    """
    try:
        resp = client.get(MI_INDEX5_URL, params={"response": "json"}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("data", [])
        if not rows:
            return None
        # 最後一列是整體市場合計
        last = rows[-1]
        # last = [date, up, limit_up, down, limit_down, flat, no_trade, no_prev]
        if len(last) < 6:
            return None
        return {
            "up":   _parse_breadth_count(str(last[1])),
            "down": _parse_breadth_count(str(last[3])),
            "flat": _parse_breadth_count(str(last[5])),
            "source": "intraday",
        }
    except Exception as exc:
        logger.debug("MI_INDEX5 intraday breadth failed: %s", exc)
        return None


def _last_trading_date() -> str:
    """Return today's date, or most recent weekday if today is weekend."""
    now = datetime.now()
    offset = max(0, now.weekday() - 4)  # Sat→1, Sun→2, weekday→0
    return (now - __import__("datetime").timedelta(days=offset)).strftime("%Y%m%d")


def _fetch_aftertrading_breadth(client: httpx.Client) -> dict[str, Any]:
    """收盤後漲跌家數：afterTrading MI_INDEX table[7]（回退到最近交易日）"""
    today = _last_trading_date()
    try:
        resp = client.get(
            MI_INDEX_URL,
            params={"response": "json", "date": today},
            timeout=8,
        )
        resp.raise_for_status()
        tables = resp.json().get("tables", [])
        if len(tables) <= 7 or not tables[7].get("data"):
            return {"up": 0, "down": 0, "flat": 0, "source": "unavailable"}

        rows = {row[0]: row[2] for row in tables[7]["data"]}  # index 2 = 股票（排除ETF/權證）
        up_str   = rows.get("上漲(漲停)", "0(0)")
        down_str = rows.get("下跌(跌停)", "0(0)")
        flat_str = rows.get("持平", "0")
        return {
            "up":   _parse_breadth_count(up_str),
            "down": _parse_breadth_count(down_str),
            "flat": int(flat_str.replace(",", "")),
            "source": "afterTrading",
        }
    except Exception as exc:
        logger.warning("MI_INDEX afterTrading breadth failed: %s", exc)
        return {"up": 0, "down": 0, "flat": 0, "source": "error"}


def _fetch_breadth(client: httpx.Client) -> dict[str, Any]:
    """
    時間感知漲跌家數：
    - 盤中 (09:00–13:40)：優先用 MI_INDEX5 即時端點
    - 其他時段：用 afterTrading MI_INDEX
    """
    now = datetime.now()
    in_market_hours = (
        now.weekday() < 5  # 平日
        and (9, 0) <= (now.hour, now.minute) <= (13, 40)
    )

    if in_market_hours:
        result = _fetch_intraday_breadth(client)
        if result is not None:
            return result
        # fallback：intraday 端點無資料時用 afterTrading
    return _fetch_aftertrading_breadth(client)


def fetch_tw_market() -> dict[str, Any]:
    """
    Fetch all TW market data in one call.
    Returns structured dict for /api/market/tw.
    On partial failure, fills with last cached values.
    """
    with httpx.Client(headers=HEADERS) as client:
        result: dict[str, Any] = {}

        # ── 加權指數 ──────────────────────────────────────────
        try:
            result["taiex"] = _fetch_mis_index("tse_t00.tw", client)
        except Exception as exc:
            logger.warning("TAIEX fetch failed: %s", exc)
            result["taiex"] = (_cache.get("tw_market") or {}).get("taiex", _zero_index())

        # ── OTC 櫃買指數 ──────────────────────────────────────
        try:
            result["otc"] = _fetch_mis_index("otc_o00.tw", client)
        except Exception as exc:
            logger.warning("OTC fetch failed: %s", exc)
            result["otc"] = (_cache.get("tw_market") or {}).get("otc", _zero_index())

        # ── 漲跌家數 ──────────────────────────────────────────
        result["breadth"] = _fetch_breadth(client)

    with _lock:
        _cache["tw_market"] = result
        _cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("tw_market refreshed — TAIEX: %s", result["taiex"]["price"])
    return result


def _zero_index() -> dict[str, Any]:
    return {
        "price": 0, "prev_close": 0, "open": 0, "high": 0, "low": 0,
        "change": 0, "change_pct": 0, "trade_value_bn": 0, "update_time": "",
    }


def get_cached_tw_market() -> dict[str, Any]:
    with _lock:
        data = _cache.get("tw_market")
    return data if data is not None else fetch_tw_market()


def get_tw_cache_meta() -> dict[str, Any]:
    with _lock:
        return {"updated_at": _cache.get("updated_at")}
