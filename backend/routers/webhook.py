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
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from utils.telegram import send_message
from utils.webhook_auth import verify_hmac

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

try:
    import redis.asyncio as aioredis
    _redis: aioredis.Redis | None = aioredis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    _redis = None


# ── DB ────────────────────────────────────────────────────────────────────────

def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "stockradar"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
    )


def _insert_tv_signal(
    strategy_id: str,
    symbol: str,
    target_position: int,
    actual_position: int,
    diff: int,
    dedup_key: str,
    status: str,
    ai_confidence: float | None = None,
) -> int:
    sql = """
    INSERT INTO tv_signals
        (strategy_id, symbol, target_position, actual_position, diff,
         dedup_key, status, ai_confidence)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (
            strategy_id, symbol, target_position, actual_position, diff,
            dedup_key, status, ai_confidence,
        ))
        signal_id = cur.fetchone()[0]
        conn.commit()
    return signal_id


def _update_tv_signal(signal_id: int, status: str, ai_confidence: float | None = None) -> None:
    sql = "UPDATE tv_signals SET status=%s, ai_confidence=%s, executed_at=NOW() WHERE id=%s"
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, ai_confidence, signal_id))
        conn.commit()


def _insert_order(
    signal_id: int,
    symbol: str,
    action: str,
    quantity: int,
    price: float | None,
    status: str,
    broker_order_id: str | None,
) -> None:
    sql = """
    INSERT INTO orders (tv_signal_id, symbol, action, quantity, price, status, broker_order_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (signal_id, symbol, action, quantity, price, status, broker_order_id))
        conn.commit()


# ── Redis dedup ───────────────────────────────────────────────────────────────

async def _is_duplicate(dedup_key: str) -> bool:
    """Return True and set key (TTL 60 s) if this is a duplicate."""
    if _redis is None:
        return False
    try:
        # SET NX EX: only set if not exists; returns None if already existed
        result = await _redis.set(f"tv_dedup:{dedup_key}", "1", nx=True, ex=60)
        return result is None   # None → key already existed → duplicate
    except Exception as exc:
        logger.warning("Redis dedup check failed: %s", exc)
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

    # ── 2. Redis dedup ────────────────────────────────────────
    if await _is_duplicate(dedup_key):
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
    from main import _broker
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

    # ── 6. 寫入 tv_signals（pending） ─────────────────────────
    signal_id = _insert_tv_signal(
        strategy_id=payload.strategy_id, symbol=symbol,
        target_position=payload.target_position,
        actual_position=actual_position, diff=diff,
        dedup_key=dedup_key, status="pending",
        ai_confidence=ai_confidence,
    )

    # ── 7. 下單 ───────────────────────────────────────────────
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
    except Exception as exc:
        _update_tv_signal(signal_id, "error", ai_confidence)
        _insert_order(signal_id, symbol, action, quantity, None, "error", None)
        order_status = "error"
        logger.error("webhook order failed: %s", exc)

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


@router.get("/api/webhook/signals")
def get_signals(limit: int = 20):
    """最近的 webhook 信號記錄（從 DB 查詢）。"""
    try:
        with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM tv_signals ORDER BY created_at DESC LIMIT %s", (limit,)
            )
            return cur.fetchall()
    except Exception as exc:
        logger.error("get_signals failed: %s", exc)
        return []
