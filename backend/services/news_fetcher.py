"""
市場快訊：從鉅亨網抓台股新聞，快取 10 分鐘
"""
import time
from datetime import datetime, timezone, timedelta

import httpx

_TW = timezone(timedelta(hours=8))
_CNYES_URL = "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TaiwanStockRadar/1.0)"}

_cache: dict = {"ts": 0, "items": []}
_CACHE_TTL = 600  # 10 minutes


def _classify_tag(title: str) -> str:
    bullish = ["創高", "大漲", "買超", "利多", "獲利", "增資", "回購", "配息", "上調", "看好", "突破", "新高", "升評", "目標價上調"]
    bearish = ["大跌", "賣超", "利空", "虧損", "下調", "獲利警告", "裁員", "下修", "看壞", "跌破"]
    cautious = ["聯準會", "Fed", "升息", "降息", "觀察", "警告", "風險", "通膨", "鷹派", "波動", "不確定"]
    for kw in bearish:
        if kw in title:
            return "利空"
    for kw in bullish:
        if kw in title:
            return "利多"
    for kw in cautious:
        if kw in title:
            return "注意"
    return "中性"


def fetch_market_news(limit: int = 8) -> list[dict]:
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL and _cache["items"]:
        return _cache["items"]

    try:
        r = httpx.get(
            _CNYES_URL,
            params={"page": 1, "limit": limit},
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        raw_items = r.json().get("items", {}).get("data", [])

        items = []
        for it in raw_items:
            ts = it.get("publishAt", 0)
            dt = datetime.fromtimestamp(ts, tz=_TW)
            items.append({
                "time":  dt.strftime("%H:%M"),
                "date":  dt.strftime("%m/%d"),
                "text":  it.get("title", ""),
                "tag":   _classify_tag(it.get("title", "")),
                "url":   f"https://news.cnyes.com/news/id/{it.get('newsId', '')}",
            })

        _cache["ts"] = now
        _cache["items"] = items
        return items

    except Exception:
        return _cache["items"] or []
