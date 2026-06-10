"""
Stock pool service — persists watched tickers in PostgreSQL stock_pool table.
"""
import logging
import os

import psycopg2
import psycopg2.extras

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


def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "stockradar"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
    )


def ensure_table() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS stock_pool (
        symbol     VARCHAR(16) PRIMARY KEY,
        name       VARCHAR(64) NOT NULL DEFAULT '',
        enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP   NOT NULL DEFAULT NOW()
    );
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(ddl)
            # seed defaults only if table is empty
            cur.execute("SELECT COUNT(*) FROM stock_pool")
            if cur.fetchone()[0] == 0:
                psycopg2.extras.execute_batch(
                    cur,
                    "INSERT INTO stock_pool (symbol, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    _DEFAULT_POOL,
                )
            conn.commit()
        logger.info("stock_pool table ready")
    except Exception as e:
        logger.error("stock_pool ensure_table failed: %s", e)


def get_pool(enabled_only: bool = True) -> list[dict]:
    """Return list of {symbol, name, enabled} from DB."""
    sql = "SELECT symbol, name, enabled FROM stock_pool"
    if enabled_only:
        sql += " WHERE enabled = TRUE"
    sql += " ORDER BY symbol"
    try:
        with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_pool failed: %s", e)
        # DB unavailable — return built-in defaults so the app still works
        return [{"symbol": s, "name": n, "enabled": True} for s, n in _DEFAULT_POOL]


def get_tickers(suffix: str = ".TW") -> list[str]:
    """Return enabled symbols as yfinance-style tickers (e.g. '2330.TW')."""
    return [f"{r['symbol']}{suffix}" for r in get_pool()]


def add_stock(symbol: str, name: str = "") -> dict:
    sql = """
        INSERT INTO stock_pool (symbol, name, enabled)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (symbol) DO UPDATE SET enabled = TRUE, name = EXCLUDED.name
        RETURNING symbol, name, enabled
    """
    with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (symbol.upper(), name))
        row = dict(cur.fetchone())
        conn.commit()
    return row


def remove_stock(symbol: str) -> bool:
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM stock_pool WHERE symbol = %s", (symbol.upper(),))
        deleted = cur.rowcount
        conn.commit()
    return deleted > 0
