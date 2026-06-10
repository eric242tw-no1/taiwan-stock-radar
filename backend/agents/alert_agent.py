"""
警報偵測 Agent
- 漲跌停：價格變動 >= 9.5% 或 <= -9.5%（台股 ±10% 限制）
- 大單：單筆成交張數 >= 閾值（預設 500 張）
每分鐘由 APScheduler 呼叫一次。
"""
import os
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.telegram import send_message, fmt_limit_alert, fmt_large_order_alert

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
LARGE_ORDER_THRESHOLD = int(os.getenv("LARGE_ORDER_THRESHOLD", "500"))  # 張
LIMIT_TRIGGER_PCT = float(os.getenv("LIMIT_TRIGGER_PCT", "9.5"))        # %

# 避免重複推播：記憶已發送的 key（進程級，簡單防重）
_sent: set[str] = set()


async def check_alerts(watchlist: list[dict]) -> None:
    """
    watchlist 格式：[{"symbol": "2330", "name": "台積電"}, ...]
    從 FinMind 拉今日即時報價，觸發條件時推播。
    """
    tw_date = _tw_today()
    for stock in watchlist:
        symbol = stock["symbol"]
        name = stock.get("name", symbol)
        try:
            data = await _fetch_realtime(symbol, tw_date)
        except Exception:
            continue

        if not data:
            continue

        price = data.get("close") or data.get("price", 0)
        open_price = data.get("open", 0)
        volume_lot = data.get("Trading_Volume", 0) // 1000  # 股 → 張

        if open_price and price:
            pct = (price - open_price) / open_price * 100
            _check_limit(symbol, name, price, pct)

        if volume_lot >= LARGE_ORDER_THRESHOLD:
            _check_large_order(symbol, name, volume_lot, price)


def _check_limit(symbol: str, name: str, price: float, pct: float) -> None:
    if abs(pct) < LIMIT_TRIGGER_PCT:
        return
    direction = "up" if pct > 0 else "down"
    key = f"limit:{symbol}:{direction}:{_tw_today()}"
    if key in _sent:
        return
    _sent.add(key)
    import asyncio
    asyncio.create_task(
        send_message(fmt_limit_alert(symbol, name, direction, price, pct))
    )


def _check_large_order(symbol: str, name: str, volume: int, price: float) -> None:
    # 大買 / 大賣以當日漲跌方向判斷
    side = "buy" if price > 0 else "sell"  # 簡化：有成交即算買方
    key = f"large:{symbol}:{_tw_today()}:{volume}"
    if key in _sent:
        return
    _sent.add(key)
    import asyncio
    asyncio.create_task(
        send_message(fmt_large_order_alert(symbol, name, side, volume, price))
    )


async def _fetch_realtime(symbol: str, date: str) -> Optional[dict]:
    """從 FinMind 拉當日即時成交資料（最後一筆）。"""
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": symbol,
        "start_date": date,
        "token": FINMIND_TOKEN,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)
    r.raise_for_status()
    records = r.json().get("data", [])
    return records[-1] if records else None


def _tw_today() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")
