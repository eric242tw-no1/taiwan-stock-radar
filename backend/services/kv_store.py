"""
SQLite KV 快取 — 取代 Redis 的跨重啟快取（單機單行程部署）。
共用主 DB 的 cache 表（key / value / expires_at）；過期資料讀取時濾除、寫入時順手清理。
"""
import logging

logger = logging.getLogger(__name__)


def kv_get(key: str) -> str | None:
    from db import get_conn
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM cache WHERE key=? AND expires_at > datetime('now')",
                (key,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning("kv_get failed [%s]: %s", key, e)
        return None


def kv_set(key: str, value: str, ttl: int) -> None:
    from db import get_conn
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) "
                "VALUES (?, ?, datetime('now', ? || ' seconds'))",
                (key, value, str(int(ttl))),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("kv_set failed [%s]: %s", key, e)
