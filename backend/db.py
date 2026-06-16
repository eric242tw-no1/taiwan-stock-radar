"""Unified SQLite connection module. All routers and services use get_conn()."""
import os
import sqlite3


def get_conn() -> sqlite3.Connection:
    db_path = os.getenv("DB_PATH", "./data/stockradar.db")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
