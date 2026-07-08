"""
TradingView Webhook — Change D (stateful, HMAC-signed, DB-persisted)

New payload (POST /api/webhook/tradingview):
{
  "strategy_id": "swing_v1",
  "symbol":      "2330",
  "secret":      "<TV_WEBHOOK_SECRET>",
  "target_position": 1000,   # shares, 0 = full exit
  "timestamp":   1718000000  # unix seconds from TradingView {{timenow}}
}

Flow: HMAC → dedup → diff → RiskManager.check_max_drawdown → Devil's Advocate → order → DB
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from utils.telegram import send_message
from utils.webhook_auth import verify_hmac
from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])

# ── DB ────────────────────────────────────────────────────────────────────────

def _insert_tv_signal(
    strategy_id: str,
    symbol: str,
    target_position: int,
    actual_position: int,
    diff: int,
    dedup_key: str,
    status: str,
    ai_confidence: float | None = None,
    reentry_action: str | None = None,
) -> int:
    sql = """
    INSERT INTO tv_signals
        (strategy_id, symbol, target_position, actual_position, diff,
         dedup_key, status, ai_confidence, reentry_action)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, (
        strategy_id, symbol, target_position, actual_position, diff,
        dedup_key, status, ai_confidence, reentry_action,
    ))
    signal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return signal_id


def _update_tv_signal(signal_id: int, status: str, ai_confidence: float | None = None) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE tv_signals SET status=?, ai_confidence=?, executed_at=datetime('now') WHERE id=?",
        (status, ai_confidence, signal_id),
    )
    conn.commit()
    conn.close()


def _insert_order(
    signal_id: int,
    symbol: str,
    action: str,
    quantity: int,
    price: float | None,
    status: str,
    broker_order_id: str | None,
) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO orders (tv_signal_id, symbol, action, quantity, price, status, broker_order_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (signal_id, symbol, action, quantity, price, status, broker_order_id),
    )
    conn.commit()
    conn.close()


# ── 訊號去重（行程內 TTL dict，語意同原 Redis SET NX EX 60s）──────────────────

_DEDUP_TTL = 60
_dedup_seen: dict[str, float] = {}   # dedup_key → expires_at (monotonic)


def _is_duplicate(dedup_key: str) -> bool:
    """Return True and set key (TTL 60 s) if this is a duplicate."""
    now = time.monotonic()
    for k, exp in list(_dedup_seen.items()):
        if exp <= now:
            del _dedup_seen[k]
    if dedup_key in _dedup_seen:
        return True
    _dedup_seen[dedup_key] = now + _DEDUP_TTL
    return False


def _build_dedup_key(strategy_id: str, symbol: str, timestamp: int) -> str:
    bucket = timestamp // 60
    return f"{strategy_id}:{symbol}:{bucket}"


# ── Payload ───────────────────────────────────────────────────────────────────

class TVPayload(BaseModel):
    strategy_id: str
    symbol: str
    secret: str
    target_position: int
    timestamp: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tw_now() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _clean_symbol(raw: str) -> str:
    return raw.replace("TWSE:", "").replace("TSE:", "").replace("TW:", "").upper()


# ── Stateful endpoint ────────────────────────────────────────────────────────

@router.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """
    Change D stateful webhook.
    Validates HMAC secret, deduplicates, calculates position diff,
    runs Devil's Advocate AI, then places order.
    """
    body = await request.body()

    # ── 1. HMAC 驗證 ──────────────────────────────────────────
    # TradingView embeds the secret inside the payload; we compare with
    # hmac.compare_digest to prevent timing attacks.
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    tv_secret = os.getenv("TV_WEBHOOK_SECRET", "")
    if tv_secret and not hmac.compare_digest(raw.get("secret", ""), tv_secret):
        raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        payload = TVPayload(**raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    symbol = _clean_symbol(payload.symbol)
    dedup_key = _build_dedup_key(payload.strategy_id, symbol, payload.timestamp)

    # ── 2. Dedup ──────────────────────────────────────────────
    if _is_duplicate(dedup_key):
        _insert_tv_signal(
            strategy_id=payload.strategy_id,
            symbol=symbol,
            target_position=payload.target_position,
            actual_position=0,
            diff=0,
            dedup_key=dedup_key + f":{payload.timestamp}",  # make unique in DB
            status="deduped",
        )
        logger.info("deduped signal %s", dedup_key)
        return {"status": "deduped", "symbol": symbol}

    # ── 3. 持倉 diff 計算 ─────────────────────────────────────
    from scheduler_tasks import _broker
    actual_position = await _broker.get_position(symbol)
    diff = payload.target_position - actual_position
    if diff == 0:
        return {"status": "no_change", "symbol": symbol, "position": actual_position}

    action = "buy" if diff > 0 else "sell"
    quantity = abs(diff)

    # ── 4. RiskManager.check_max_drawdown ─────────────────────
    from services.risk_manager import RiskManager
    drawdown_decision = RiskManager().check_max_drawdown()
    if not drawdown_decision.approved:
        _insert_tv_signal(
            strategy_id=payload.strategy_id, symbol=symbol,
            target_position=payload.target_position,
            actual_position=actual_position, diff=diff,
            dedup_key=dedup_key, status="rejected",
        )
        return {"status": "rejected", "reason": drawdown_decision.reason, "symbol": symbol}

    # ── 5. Devil's Advocate ───────────────────────────────────
    from agents.ai_engine import devil_advocate
    da = await devil_advocate(symbol, action, payload.target_position, diff)
    ai_confidence = da["confidence"]

    if not da["approved"]:
        signal_id = _insert_tv_signal(
            strategy_id=payload.strategy_id, symbol=symbol,
            target_position=payload.target_position,
            actual_position=actual_position, diff=diff,
            dedup_key=dedup_key, status="rejected",
            ai_confidence=ai_confidence,
        )
        await send_message(
            f"🛑 <b>[Webhook] Devil's Advocate 拒絕</b>\n"
            f"股票：<b>{symbol}</b>　信心：{ai_confidence:.0%}\n"
            f"理由：{da['reason']}\n時間：{_tw_now()}"
        )
        return {"status": "rejected", "reason": da["reason"], "symbol": symbol,
                "ai_confidence": ai_confidence}

    # ── 6. ReEntry 評估（買入信號才需要）────────────────────────
    reentry_action: str | None = None
    if action == "buy":
        from services.reentry_evaluator import evaluate as re_evaluate
        positions = []
        try:
            positions = await _broker.get_positions()
        except Exception:
            pass
        reentry_action = re_evaluate(symbol, ai_confidence, positions)

        if reentry_action == "ignore":
            signal_id = _insert_tv_signal(
                strategy_id=payload.strategy_id, symbol=symbol,
                target_position=payload.target_position,
                actual_position=actual_position, diff=diff,
                dedup_key=dedup_key, status="ignored",
                ai_confidence=ai_confidence, reentry_action=reentry_action,
            )
            logger.info("ReEntry ignore: %s confidence=%.2f", symbol, ai_confidence)
            return {"status": "ignored", "reason": "reentry_low_confidence", "symbol": symbol}

        if reentry_action == "warn":
            signal_id = _insert_tv_signal(
                strategy_id=payload.strategy_id, symbol=symbol,
                target_position=payload.target_position,
                actual_position=actual_position, diff=diff,
                dedup_key=dedup_key, status="warned",
                ai_confidence=ai_confidence, reentry_action=reentry_action,
            )
            await send_message(
                f"⚠️ <b>[ReEntry 警告]</b> {symbol}\n"
                f"已有持倉，AI 信心 {ai_confidence:.0%} 未達加碼門檻（75%）\n"
                f"建議觀察，未自動下單。"
            )
            return {"status": "warned", "reason": "reentry_warn", "symbol": symbol}

        # reentry_action == "add"：有持倉加碼時減半下單
        has_position = any(p.get("symbol") == symbol for p in positions)
        if has_position:
            quantity = max(1, quantity // 2)

    # ── 7. 寫入 tv_signals（pending）────────────────────────────
    signal_id = _insert_tv_signal(
        strategy_id=payload.strategy_id, symbol=symbol,
        target_position=payload.target_position,
        actual_position=actual_position, diff=diff,
        dedup_key=dedup_key, status="pending",
        ai_confidence=ai_confidence, reentry_action=reentry_action,
    )

    # ── 8. Telegram 確認（等待 callback，最多 60 秒）────────────
    from utils.telegram import send_order_confirm
    from utils.telegram_bot import register_pending, is_confirmed

    try:
        quote = await _broker.get_quote(symbol)
        entry_price = float(quote.get("price", 0))
    except Exception:
        entry_price = 0.0
    stop_price = round(entry_price * 0.95, 2)

    confirm_event = register_pending(signal_id)
    await send_order_confirm(
        signal_id=signal_id, symbol=symbol,
        qty=quantity, price=entry_price, stop_price=stop_price,
    )

    try:
        await asyncio.wait_for(confirm_event.wait(), timeout=60)
    except asyncio.TimeoutError:
        _update_tv_signal(signal_id, "timeout", ai_confidence)
        await send_message(f"⏱️ 下單逾時取消：{symbol}（60 秒內未回應）")
        return {"status": "timeout", "symbol": symbol, "signal_id": signal_id}

    if not is_confirmed(signal_id):
        _update_tv_signal(signal_id, "cancelled", ai_confidence)
        return {"status": "cancelled", "symbol": symbol, "signal_id": signal_id}

    # ── 9. 下單 ───────────────────────────────────────────────
    broker_order_id = None
    try:
        result = await _broker.place_order(
            symbol=symbol, action=action,
            order_type="market", quantity=quantity,
        )
        broker_order_id = result.get("order_id", "")
        _update_tv_signal(signal_id, "executed", ai_confidence)
        _insert_order(signal_id, symbol, action, quantity, None, "submitted", broker_order_id)
        order_status = "submitted"

        # 買入成功 → 立即啟動 StopLossGuard 雙層保護
        if action == "buy":
            from scheduler_tasks import stop_loss_guard
            try:
                await stop_loss_guard.setup(
                    symbol=symbol, quantity=quantity,
                    stop_price=stop_price, entry_price=entry_price,
                )
            except Exception as slg_exc:
                logger.warning("StopLossGuard setup failed [%s]: %s", symbol, slg_exc)
    except Exception as exc:
        _update_tv_signal(signal_id, "error", ai_confidence)
        _insert_order(signal_id, symbol, action, quantity, None, "error", None)
        order_status = "error"
        logger.error("webhook order failed: %s", exc)

    # 推播訊號至 SSE stream（供前端 useSignalStream 使用）
    try:
        import json as _json
        from services.signal_bus import publish as _publish_signal
        _publish_signal(_json.dumps({
            "signal_id": signal_id, "symbol": symbol, "action": action,
            "quantity": quantity, "ai_confidence": ai_confidence,
            "order_status": order_status, "timestamp": _tw_now(),
        }, ensure_ascii=False))
    except Exception as _pub_exc:
        logger.warning("webhook: signal publish failed — %s", _pub_exc)

    await send_message(
        f"{'📈' if action == 'buy' else '📉'} <b>[Webhook] {action.upper()}</b>\n"
        f"股票：<b>{symbol}</b>　數量：{quantity} 股\n"
        f"AI 信心：{ai_confidence:.0%}　委託：{order_status}\n"
        f"時間：{_tw_now()}"
    )

    return {
        "status": order_status,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "ai_confidence": ai_confidence,
        "signal_id": signal_id,
        "broker_order_id": broker_order_id,
    }


class TVLegacyPayload(BaseModel):
    symbol: str
    action: str      # "buy" | "sell"
    quantity: int
    price: float | None = None
    strategy_id: str = "legacy"


@router.post("/api/webhook/tradingview-legacy")
async def tradingview_webhook_legacy(payload: TVLegacyPayload):
    """
    Action-based legacy webhook (deprecated 2026-06-13).
    Scheduled for removal 2026-06-20. Migrate to /api/webhook/tradingview.
    """
    logger.warning(
        "DEPRECATED: /tradingview-legacy called for %s %s x%d — "
        "please migrate to /api/webhook/tradingview",
        payload.action, payload.symbol, payload.quantity,
    )
    symbol = _clean_symbol(payload.symbol)
    return {
        "status": "legacy_received",
        "symbol": symbol,
        "action": payload.action,
        "quantity": payload.quantity,
        "warning": "This endpoint is deprecated. Migrate to /api/webhook/tradingview with target_position.",
        "migration_deadline": "2026-06-20",
    }


@router.get("/api/webhook/signals")
def get_signals(limit: int = 20):
    """最近的 webhook 信號記錄（從 DB 查詢）。"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tv_signals ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        logger.error("get_signals failed: %s", exc)
        return []
