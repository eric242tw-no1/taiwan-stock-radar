"""
SSE 即時行情串流
- /api/stream/quote/{symbol}  每 5 秒推播個股報價
- /api/stream/market           每 10 秒推播大盤指數
- /api/stream/signals          即時 TradingView 訊號推播（Redis Pub/Sub）
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

_SIGNAL_CHANNEL = "tv_signals"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/quote/{symbol}")
async def stream_quote(symbol: str):
    """
    SSE 推播個股即時報價。
    優先使用 Shioaji Tick（SinopacBroker），fallback 至 TWSE MIS 每 5 秒輪詢。
    前端：const es = new EventSource('/api/stream/quote/2330')
    """
    sym = symbol.upper()

    async def generator():
        from main import _broker
        from brokers.sinopac import SinopacBroker

        if isinstance(_broker, SinopacBroker):
            # Shioaji Tick 模式：subscribe_tick 透過 callback 推入 Queue
            q: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _on_tick(tick: dict):
                loop.call_soon_threadsafe(q.put_nowait, tick)

            try:
                _broker.subscribe_tick(sym, _on_tick)
                while True:
                    tick = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"event: tick\ndata: {json.dumps(tick, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield f"event: tick\ndata: {json.dumps({'symbol': sym, 'error': 'tick timeout'})}\n\n"
            except Exception as e:
                logger.warning("SSE Shioaji tick error [%s]: %s", sym, e)
                # fallthrough to polling below
        else:
            # TWSE MIS 輪詢 fallback
            from services.stock_quote_fetcher import fetch_stock_quote
            while True:
                try:
                    loop = asyncio.get_event_loop()
                    quote = await loop.run_in_executor(None, fetch_stock_quote, sym)
                    yield f"event: tick\ndata: {json.dumps(quote, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.warning("SSE quote error [%s]: %s", sym, e)
                    yield f"event: tick\ndata: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/market")
async def stream_market():
    """
    SSE 推播大盤指數（加權/OTC/期指/匯率），每 10 秒更新
    前端：const es = new EventSource('/api/stream/market')
    """
    async def generator():
        from services.twse_fetcher import get_cached_tw_market
        from services.taifex_fetcher import get_cached_futures_and_fx
        while True:
            try:
                tw = get_cached_tw_market()
                fx = get_cached_futures_and_fx()
                payload = {
                    "taiex": tw.get("taiex"),
                    "otc":   tw.get("otc"),
                    "futures": fx.get("futures"),
                    "usd_twd": fx.get("usd_twd"),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning("SSE market error: %s", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/signals")
async def stream_signals():
    """
    SSE 推播即時 TradingView 策略訊號（Redis Pub/Sub）。
    前端：const es = new EventSource('/api/stream/signals')
    每 30 秒發送 heartbeat 避免連線逾時。
    """
    async def generator():
        import redis.asyncio as aioredis

        r = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(_SIGNAL_CHANNEL)
        heartbeat_interval = 30
        last_heartbeat = asyncio.get_event_loop().time()

        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("data"):
                    yield f"data: {msg['data']}\n\n"

                now = asyncio.get_event_loop().time()
                if now - last_heartbeat >= heartbeat_interval:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(_SIGNAL_CHANNEL)
            await r.aclose()

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/portfolio")
async def stream_portfolio():
    """
    SSE 推播元大持倉，每 30 秒更新。
    前端：const es = new EventSource('/api/stream/portfolio')
    """
    async def generator():
        from main import _broker
        while True:
            try:
                positions = await _broker.get_positions()
                balance   = await _broker.get_balance()
                payload = {
                    "simulation": getattr(_broker, "simulation", True),
                    "positions":  positions,
                    "summary": {
                        "total_value":  balance.get("total_value", 0),
                        "cash":         balance.get("cash", 0),
                        "margin_usage": balance.get("margin_usage", 0),
                    },
                    "updated_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone(__import__("datetime").timedelta(hours=8))
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "error": None,
                }
            except Exception as exc:
                payload = {"error": str(exc), "positions": [], "simulation": True}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(30)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
