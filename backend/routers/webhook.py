"""
TradingView Webhook 端點
POST /api/webhook/tradingview

TradingView Alert Message 格式：
{
  "symbol": "{{ticker}}",
  "action": "buy" | "sell",
  "price": {{close}},
  "indicator": "MACD_CROSS",
  "timeframe": "{{interval}}",
  "timestamp": "{{time}}"
}

安全：Header X-TV-Secret 需與環境變數 TV_WEBHOOK_SECRET 相符。
未設定 secret 時跳過驗證（開發模式）。
"""
import os
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from utils.telegram import send_message

router = APIRouter(tags=["webhook"])

TV_SECRET = os.getenv("TV_WEBHOOK_SECRET", "")

# 最近 100 筆信號 in-memory（之後換 Redis）
_signal_log: list[dict] = []

ACTION_LABEL = {"buy": ("📈", "買入信號"), "sell": ("📉", "賣出信號")}
INDICATOR_ZH = {
    "MACD_CROSS":    "MACD 黃金交叉",
    "RSI_OVERSOLD":  "RSI 超賣反彈",
    "MA20_BREAKOUT": "突破 MA20",
    "CUSTOM":        "自訂信號",
}


@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    body = await request.body()

    # 驗證 secret（有設定才驗）
    if TV_SECRET:
        incoming = request.headers.get("X-TV-Secret", "")
        if not hmac.compare_digest(incoming, TV_SECRET):
            raise HTTPException(status_code=401, detail="Invalid secret")

    try:
        signal = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    symbol = (
        signal.get("symbol", "")
        .replace("TWSE:", "")
        .replace("TSE:", "")
        .replace("TW:", "")
        .upper()
    )
    action = signal.get("action", "").lower()
    price = signal.get("price", 0)
    indicator = signal.get("indicator", "CUSTOM")
    timeframe = signal.get("timeframe", "")

    # 記錄
    record = {
        "symbol": symbol,
        "action": action,
        "price": price,
        "indicator": indicator,
        "timeframe": timeframe,
        "received_at": _tw_now(),
    }
    _signal_log.append(record)
    if len(_signal_log) > 100:
        _signal_log.pop(0)

    # Telegram 推播
    icon, label = ACTION_LABEL.get(action, ("🔔", "信號"))
    ind_zh = INDICATOR_ZH.get(indicator, indicator)
    text = (
        f"{icon} <b>[TradingView] {label}</b>\n"
        f"股票：<b>{symbol}</b>\n"
        f"指標：{ind_zh}"
        + (f"（{timeframe}）" if timeframe else "") + "\n"
        f"價格：<b>{price}</b>\n"
        f"時間：{_tw_now()}"
    )
    await send_message(text)

    return {"status": "received", "symbol": symbol, "action": action}


@router.get("/api/webhook/signals")
def get_signals(limit: int = 20):
    """查看最近收到的信號紀錄。"""
    return _signal_log[-limit:]


def _tw_now() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
