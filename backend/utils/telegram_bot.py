"""
Telegram Bot polling loop（python-telegram-bot v20+ async API）

啟動方式：在 main.py lifespan 中以 asyncio.create_task 執行 run_polling()。
掛單確認流程：
  1. webhook 呼叫 register_pending(signal_id) 取得 asyncio.Event
  2. 使用者按下 Inline Keyboard → CallbackQueryHandler → resolve_pending()
  3. webhook 以 asyncio.wait_for(event, timeout=60) 等待結果
"""
import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── 待確認下單表 ──────────────────────────────────────────────────────────────
# signal_id → {"event": asyncio.Event, "confirmed": bool}
_pending: dict[int, dict[str, Any]] = {}


def register_pending(signal_id: int) -> asyncio.Event:
    """webhook 呼叫：登記待確認訊號，回傳 Event 供 wait_for 等待。"""
    event = asyncio.Event()
    _pending[signal_id] = {"event": event, "confirmed": False}
    return event


def resolve_pending(signal_id: int, confirmed: bool) -> None:
    """Bot callback 呼叫：標記結果並釋放 Event。"""
    entry = _pending.pop(signal_id, None)
    if entry:
        entry["confirmed"] = confirmed
        entry["event"].set()


def is_confirmed(signal_id: int) -> bool:
    """webhook 在 Event.set() 後呼叫，取得最終決策。"""
    # 已被 resolve_pending pop 出，查不到即為已處理
    return _pending.get(signal_id, {}).get("confirmed", False)


# ── Bot polling ───────────────────────────────────────────────────────────────

async def run_polling() -> None:
    """Telegram Bot polling loop；在 main.py asyncio background task 中執行。"""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN 未設定，跳過 bot polling")
        return

    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CallbackQueryHandler,
            CommandHandler,
            ContextTypes,
        )
    except ImportError:
        logger.warning("python-telegram-bot 未安裝，跳過 bot polling")
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("台股AI雷達 Bot 已就緒 ✅\n下單確認請求將在此推播。")

    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        data: str = query.data or ""
        parts = data.split(":", 1)
        if len(parts) != 2:
            return

        action, sid_str = parts
        try:
            signal_id = int(sid_str)
        except ValueError:
            return

        if action == "confirm":
            resolve_pending(signal_id, confirmed=True)
            await query.edit_message_text(
                f"✅ 下單已確認（Signal #{signal_id}）\n正在送出委託…"
            )
        elif action == "cancel":
            resolve_pending(signal_id, confirmed=False)
            await query.edit_message_text(
                f"❌ 下單已取消（Signal #{signal_id}）"
            )
        elif action == "analysis":
            # 不影響待確認狀態，僅回覆提示
            await query.answer("請至 AI 分析頁查看詳細報告", show_alert=True)

    app = (
        Application.builder()
        .token(token)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Telegram bot polling 已啟動")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        # 永久等待直到任務被取消
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            await app.updater.stop()
            await app.stop()
    logger.info("Telegram bot polling 已停止")
