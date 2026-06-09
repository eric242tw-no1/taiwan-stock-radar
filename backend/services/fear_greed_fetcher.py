"""
恐懼與貪婪指數
資料來源：alternative.me（加密市場情緒）
每日更新，快取24小時
"""
import logging
import threading
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_lock  = threading.Lock()
_cache: dict = {"ts": 0, "data": None}

LABEL_MAP = {
    "Extreme Fear":  "極度恐懼",
    "Fear":          "恐懼",
    "Neutral":       "中立",
    "Greed":         "貪婪",
    "Extreme Greed": "極度貪婪",
}


def _classify(v: int) -> str:
    if v >= 75: return "Extreme Greed"
    if v >= 55: return "Greed"
    if v >= 45: return "Neutral"
    if v >= 25: return "Fear"
    return "Extreme Fear"


def fetch_fear_greed() -> dict:
    global _cache
    with _lock:
        if _cache["data"] and time.time() - _cache["ts"] < 3600:
            return _cache["data"]

    try:
        resp = httpx.get(
            "https://api.alternative.me/fng/",
            params={"limit": 365},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json()["data"]   # newest first

        def pick(idx: int) -> dict | None:
            if idx < len(items):
                v = int(items[idx]["value"])
                cls = items[idx].get("value_classification") or _classify(v)
                ts  = int(items[idx]["timestamp"])
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y/%m/%d")
                return {"value": v, "label": LABEL_MAP.get(cls, cls), "date": date_str}
            return None

        # 找「約30天前」和「約365天前」的索引
        def find_idx(target_days: int) -> int:
            target_ts = items[0]["timestamp"]
            base = int(items[0]["timestamp"])
            target = base - target_days * 86400
            best, best_i = 9e9, 0
            for i, it in enumerate(items):
                diff = abs(int(it["timestamp"]) - target)
                if diff < best:
                    best, best_i = diff, i
            return best_i

        result = {
            "today":       pick(0),
            "yesterday":   pick(1),
            "week_ago":    pick(7),
            "month_ago":   pick(find_idx(30)),
            "year_ago":    pick(find_idx(365)),
            "source":      "alternative.me",
        }

        with _lock:
            _cache = {"ts": time.time(), "data": result}
        return result

    except Exception as e:
        logger.error("fear_greed fetch failed: %s", e)
        with _lock:
            return _cache.get("data") or {"error": str(e)}


def get_cached_fear_greed() -> dict:
    with _lock:
        if _cache["data"] and time.time() - _cache["ts"] < 3600:
            return _cache["data"]
    return fetch_fear_greed()
