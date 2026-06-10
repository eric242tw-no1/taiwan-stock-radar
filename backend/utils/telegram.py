"""Telegram Bot 推播工具"""
import os
import httpx
from typing import Optional

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(text: str, chat_id: Optional[str] = None, parse_mode: str = "HTML") -> bool:
    """傳送訊息到 Telegram；回傳是否成功。"""
    cid = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not cid:
        return False
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_BASE}/sendMessage",
            json={"chat_id": cid, "text": text, "parse_mode": parse_mode},
        )
    return r.status_code == 200


def fmt_limit_alert(symbol: str, name: str, direction: str, price: float, pct: float) -> str:
    icon = "🔴" if direction == "down" else "🟢"
    label = "跌停" if direction == "down" else "漲停"
    return (
        f"{icon} <b>[{label}警示] {symbol} {name}</b>\n"
        f"現價：<b>{price:.2f}</b>（{pct:+.2f}%）\n"
        f"台灣時間：{_tw_now()}"
    )


def fmt_large_order_alert(symbol: str, name: str, side: str, volume: int, price: float) -> str:
    icon = "📈" if side == "buy" else "📉"
    label = "大買單" if side == "buy" else "大賣單"
    return (
        f"{icon} <b>[{label}] {symbol} {name}</b>\n"
        f"成交量：<b>{volume:,} 張</b> @ {price:.2f}\n"
        f"台灣時間：{_tw_now()}"
    )


def _tw_now() -> str:
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
