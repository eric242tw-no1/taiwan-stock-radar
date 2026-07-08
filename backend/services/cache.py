"""
三級快取服務
L1 — 記憶體 dict，TTL 5s（同 process 極速）
L2 — Redis，TTL 60s（跨 worker 共享）
L3 — SQLite cache 表，TTL 300s（Redis 不可用時降級）
"""
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_L1_TTL = 5
_L2_TTL = 60
_L3_TTL = 300

# L1 in-memory: key → (value_json, expires_at)
_l1: dict[str, tuple[str, float]] = {}


class CacheService:
    def get(self, key: str) -> Any | None:
        # L1
        entry = _l1.get(key)
        if entry:
            val_json, exp = entry
            if time.monotonic() < exp:
                return json.loads(val_json)
            del _l1[key]

        # L2 Redis
        try:
            r = _get_redis()
            raw = r.get(f"cache:{key}")
            if raw:
                value = json.loads(raw)
                # 回填 L1
                _l1[key] = (raw if isinstance(raw, str) else raw.decode(), time.monotonic() + _L1_TTL)
                return value
        except Exception as e:
            logger.debug("CacheService L2 miss (%s): %s", key, e)

        # L3 SQLite
        try:
            value = _l3_get(key)
            if value is not None:
                return value
        except Exception as e:
            logger.debug("CacheService L3 miss (%s): %s", key, e)

        return None

    def set(self, key: str, value: Any, ttl: int = _L2_TTL) -> None:
        val_json = json.dumps(value, ensure_ascii=False)

        # L1（固定 5s，不受外部 ttl 影響）
        _l1[key] = (val_json, time.monotonic() + _L1_TTL)

        # L2 Redis
        try:
            r = _get_redis()
            r.set(f"cache:{key}", val_json, ex=min(ttl, _L2_TTL))
        except Exception as e:
            logger.debug("CacheService L2 set failed (%s): %s", key, e)

        # L3 SQLite
        try:
            _l3_set(key, val_json, ttl or _L3_TTL)
        except Exception as e:
            logger.debug("CacheService L3 set failed (%s): %s", key, e)


# ── Redis helper ──────────────────────────────────────────────────────────────

def _get_redis():
    url = os.getenv("REDIS_URL", "")
    if not url:
        raise RuntimeError("REDIS_URL not set — L2 disabled")
    import redis
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=1,
    )


# ── SQLite helpers ─────────────────────────────────────────────────────────────

def _l3_get(key: str) -> Any | None:
    from db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT value FROM cache WHERE key=? AND expires_at > datetime('now')",
            (key,),
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None
    finally:
        conn.close()


def _l3_set(key: str, val_json: str, ttl: int) -> None:
    from db import get_conn
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) "
            "VALUES (?, ?, datetime('now', ? || ' seconds'))",
            (key, val_json, str(ttl)),
        )
        conn.commit()
    finally:
        conn.close()


# 模組層級單例
cache = CacheService()
