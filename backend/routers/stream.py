"""
SSE 即時行情串流
- /api/stream/quote/{symbol}  每 5 秒推播個股報價
- /api/stream/market           每 10 秒推播大盤指數
"""
import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/quote/{symbol}")
async def stream_quote(symbol: str):
    """
    SSE 推播個股即時報價，每 5 秒更新
    前端：const es = new EventSource('/api/stream/quote/2330')
    """
    sym = symbol.upper()

    async def generator():
        from services.stock_quote_fetcher import fetch_stock_quote
        while True:
            try:
                loop = asyncio.get_event_loop()
                quote = await loop.run_in_executor(None, fetch_stock_quote, sym)
                yield f"data: {json.dumps(quote, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning("SSE quote error [%s]: %s", sym, e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
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
