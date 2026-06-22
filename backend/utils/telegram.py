"""Telegram Bot 推播工具"""
import os
import httpx
from typing import Optional

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _write_notification(message: str, source: str) -> None:
    try:
        from db import get_conn
        conn = get_conn()
        conn.execute(
            "INSERT INTO notifications (message, source) VALUES (?, ?)",
            (message[:2000], source),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 不影響主流程


async def send_message(text: str, chat_id: Optional[str] = None, parse_mode: str = "HTML", source: str = "system") -> bool:
    """傳送訊息到 Telegram；回傳是否成功。同步寫入 notifications 表。"""
    cid = chat_id or TELEGRAM_CHAT_ID
    success = False
    if TELEGRAM_BOT_TOKEN and cid:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{_BASE}/sendMessage",
                json={"chat_id": cid, "text": text, "parse_mode": parse_mode},
            )
        success = r.status_code == 200
    _write_notification(text, source if success else "failed")
    return success


async def send_order_confirm(
    signal_id: int,
    symbol: str,
    qty: int,
    price: float,
    stop_price: float,
    chat_id: Optional[str] = None,
) -> bool:
    """送出含 Inline Keyboard 的下單確認訊息。
    Callback data 格式：confirm:<signal_id> / cancel:<signal_id> / analysis:<signal_id>
    """
    cid = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not cid:
        return False

    text = (
        f"📋 <b>下單確認請求</b>\n"
        f"━━━━━━━━━━━━\n"
        f"📌 股票：<b>{symbol}</b>\n"
        f"📦 數量：<b>{qty} 張</b>\n"
        f"💰 市價：<b>{price:.2f}</b>\n"
        f"🛑 停損：<b>{stop_price:.2f}</b>\n"
        f"⏱️ 60 秒內未回應將自動取消\n"
        f"Signal ID：{signal_id}"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ 確認下單", "callback_data": f"confirm:{signal_id}"},
            {"text": "❌ 取消",     "callback_data": f"cancel:{signal_id}"},
        ], [
            {"text": "📊 查看 AI 分析", "callback_data": f"analysis:{signal_id}"},
        ]]
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_BASE}/sendMessage",
            json={
                "chat_id": cid,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            },
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
