"""Unified SQLite connection module. All routers and services use get_conn()."""
import os
import sqlite3
import threading

_local = threading.local()


class _Conn:
    """Wraps sqlite3.Connection so caller's conn.close() is a no-op —
    keeps connection alive in thread-local cache.
    """
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass  # ponytail: caller keeps calling close(), nothing to do

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass  # ponytail: context manager shouldn't close either


def get_conn() -> _Conn:
    db_path = os.getenv("DB_PATH", "./data/stockradar.db")
    wrapper = getattr(_local, 'wrapper', None)
    if wrapper is None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        wrapper = _Conn(conn)
        _local.wrapper = wrapper
    return wrapper
