"""
警報偵測 Agent
- 漲跌停：價格變動 >= 9.5% 或 <= -9.5%（台股 ±10% 限制）
- 大單：單筆成交張數 >= 閾值（預設 500 張）
- 自訂條件：price / rsi / ai_score / deviation / change_pct
每分鐘由 APScheduler 呼叫一次。
"""
import os
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.telegram import send_message, fmt_limit_alert, fmt_large_order_alert

logger = logging.getLogger(__name__)

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


def run_check_alerts_sync(watchlist: list[dict]) -> None:
    """同步包裝，供 BackgroundScheduler 呼叫。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(check_alerts(watchlist))
            loop.create_task(check_custom_rules())
        else:
            asyncio.run(check_alerts(watchlist))
            asyncio.run(check_custom_rules())
    except Exception:
        asyncio.run(check_alerts(watchlist))


# ── 自訂條件警報 ──────────────────────────────────────────────────────────────

_custom_sent: set[str] = set()

_OP_LABELS = {"gte": "≥", "lte": "≤", "gt": ">", "lt": "<"}

METRIC_LABELS = {
    "ai_score": "AI 分數",
    "rsi": "RSI",
    "price": "價格",
    "deviation": "MA20 乖離率",
    "change_pct": "漲跌幅",
}


def _eval_op(value: float, op: str, threshold: float) -> bool:
    return {"gte": value >= threshold, "lte": value <= threshold,
            "gt": value > threshold, "lt": value < threshold}.get(op, False)


async def check_custom_rules() -> None:
    """評估所有啟用的自訂警報規則，觸發時發 Telegram。"""
    try:
        from routers.alerts import _rules
    except Exception:
        return

    for rule in _rules.values():
        if not rule.get("enabled", True):
            continue
        rule_type = rule.get("type", "")
        if rule_type in ("limit", "large_order", "both", ""):
            continue  # 這些由 check_alerts 處理

        symbol = rule.get("symbol", "")
        name = rule.get("name", symbol)
        threshold = rule.get("threshold")
        op = rule.get("operator", "gte")
        rule_id = rule.get("id", 0)

        if threshold is None:
            continue

        try:
            value = await _get_metric(symbol, rule_type)
        except Exception as e:
            logger.debug("custom alert fetch error %s %s: %s", symbol, rule_type, e)
            continue

        if value is None:
            continue

        if not _eval_op(value, op, threshold):
            continue

        key = f"custom:{rule_id}:{_tw_today()}"
        if key in _custom_sent:
            continue
        _custom_sent.add(key)

        op_label = _OP_LABELS.get(op, op)
        metric_label = METRIC_LABELS.get(rule_type, rule_type)
        msg = (
            f"🔔 警報觸發\n"
            f"股票：{name}（{symbol}）\n"
            f"條件：{metric_label} {op_label} {threshold}\n"
            f"目前值：{value:.2f}\n"
            f"時間：{datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')}"
        )
        await send_message(msg)
        logger.info("custom alert sent: %s %s %s%s%s (value=%.2f)",
                    symbol, metric_label, op_label, threshold, "", value)


async def _get_metric(symbol: str, metric: str) -> Optional[float]:
    """取得個股的指定指標值。"""
    if metric == "ai_score":
        # 從 AI engine 快取讀
        try:
            from agents.ai_engine import get_ai_analysis
            result = await get_ai_analysis(symbol, force=False)
            return float(result.get("score", 0)) if result else None
        except Exception:
            return None

    # 其他指標從後端即時資料讀
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"http://127.0.0.1:8000/api/stock/{symbol}")
        if r.status_code != 200:
            return None
        data = r.json()
        mapping = {
            "price": "price",
            "rsi": "rsi_14",
            "deviation": "ma20_bias_pct",
            "change_pct": "change_pct",
        }
        key = mapping.get(metric)
        return float(data.get(key, 0)) if key else None
    except Exception:
        return None
