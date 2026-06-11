"""
三級快取架構
L1 進程內存（TTL 30 分鐘）— 最快，重啟後消失
L2 SQLite 永久存儲             — 冷快取，跨重啟保留
L3 Redis（TTL 到隔日 09:00）  — 可選，Redis 不可用時靜默降級
"""
import json
import logging
import os
import sqlite3
import time
from typing import Any

logger = logging.getLogger(__name__)

_MEM_TTL = 1800  # 30 min
_REDIS_TTL_DEFAULT = 57600  # 16 h ≈ 到隔日 09:00


class ThreeLevelCache:
    def __init__(self):
        self._mem: dict[str, Any] = {}
        self._mem_ts: dict[str, float] = {}

        self.sqlite_path = os.getenv("SQLITE_CACHE_PATH", "./cache/stock_cache.db")
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        self._init_sqlite()

        self._redis = None
        self._try_connect_redis()

    # ── init ──────────────────────────────────────────────────────────────

    def _init_sqlite(self):
        con = sqlite3.connect(self.sqlite_path)
        con.execute(
            "CREATE TABLE IF NOT EXISTS cache_store "
            "(key TEXT PRIMARY KEY, value TEXT, updated_at REAL)"
        )
        con.commit()
        con.close()

    def _try_connect_redis(self):
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return
        try:
            import redis
            r = redis.Redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            self._redis = r
            logger.info("ThreeLevelCache: Redis connected (%s)", redis_url)
        except Exception as e:
            logger.warning("ThreeLevelCache: Redis unavailable, L3 disabled — %s", e)

    # ── public API ────────────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        # L1
        if key in self._mem and time.time() - self._mem_ts[key] < _MEM_TTL:
            return self._mem[key]

        # L2
        try:
            con = sqlite3.connect(self.sqlite_path)
            row = con.execute(
                "SELECT value FROM cache_store WHERE key=?", (key,)
            ).fetchone()
            con.close()
            if row:
                data = json.loads(row[0])
                self._mem[key] = data
                self._mem_ts[key] = time.time()
                return data
        except Exception as e:
            logger.debug("ThreeLevelCache L2 get error [%s]: %s", key, e)

        # L3
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    self._mem[key] = data
                    self._mem_ts[key] = time.time()
                    return data
            except Exception as e:
                logger.debug("ThreeLevelCache L3 get error [%s]: %s", key, e)

        return None

    def set(self, key: str, value: Any, redis_ttl: int = _REDIS_TTL_DEFAULT):
        # L1
        self._mem[key] = value
        self._mem_ts[key] = time.time()

        # L2
        try:
            con = sqlite3.connect(self.sqlite_path)
            con.execute(
                "INSERT OR REPLACE INTO cache_store VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), time.time()),
            )
            con.commit()
            con.close()
        except Exception as e:
            logger.warning("ThreeLevelCache L2 set error [%s]: %s", key, e)

        # L3
        if self._redis:
            try:
                self._redis.set(
                    key,
                    json.dumps(value, ensure_ascii=False),
                    ex=redis_ttl,
                )
            except Exception as e:
                logger.debug("ThreeLevelCache L3 set error [%s]: %s", key, e)

    def delete(self, key: str):
        self._mem.pop(key, None)
        self._mem_ts.pop(key, None)
        try:
            con = sqlite3.connect(self.sqlite_path)
            con.execute("DELETE FROM cache_store WHERE key=?", (key,))
            con.commit()
            con.close()
        except Exception:
            pass
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass


# singleton
cache = ThreeLevelCache()
