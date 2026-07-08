"""
行程內訊號匯流排 — 取代 Redis Pub/Sub。
webhook 發布 TradingView 訊號，SSE /api/stream/signals 訂閱。
僅在單一 uvicorn 行程內有效；若改回 multi-worker 部署需換外部 broker。
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_MAX_QUEUE = 100

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def publish(message: str) -> None:
    """廣播已序列化的 JSON 字串給所有訂閱者；佇列滿時丟棄並記 log。"""
    for q in list(_subscribers):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("signal_bus: subscriber queue full, dropping message")
