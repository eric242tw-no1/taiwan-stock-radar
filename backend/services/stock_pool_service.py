"""Stock pool service — persists watched tickers in SQLite stock_pool table."""
import logging

from db import get_conn

logger = logging.getLogger(__name__)

_DEFAULT_POOL = [
    ("2330", "台積電"),
    ("2317", "鴻海"),
    ("2454", "聯發科"),
    ("2412", "中華電"),
    ("0050", "元大台灣50"),
    ("2308", "台達電"),
    ("2881", "富邦金"),
    ("2382", "廣達"),
]


def ensure_table() -> None:
    pass  # schema managed by schema_sqlite.sql


def get_pool(enabled_only: bool = True) -> list[dict]:
    sql = "SELECT symbol, name, enabled FROM stock_pool"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY symbol"
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error("get_pool failed: %s", e)
        return [{"symbol": s, "name": n, "enabled": True} for s, n in _DEFAULT_POOL]


def get_tickers(suffix: str = ".TW") -> list[str]:
    return [f"{r['symbol']}{suffix}" for r in get_pool()]


def add_stock(symbol: str, name: str = "") -> dict:
    conn = get_conn()
    conn.execute(
        "INSERT INTO stock_pool (symbol, name, enabled) VALUES (?, ?, 1) "
        "ON CONFLICT (symbol) DO UPDATE SET enabled=1, name=excluded.name",
        (symbol.upper(), name),
    )
    cur = conn.cursor()
    cur.execute("SELECT symbol, name, enabled FROM stock_pool WHERE symbol=?", (symbol.upper(),))
    row = dict(cur.fetchone())
    conn.commit()
    conn.close()
    return row


def remove_stock(symbol: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM stock_pool WHERE symbol = ?", (symbol.upper(),))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0
