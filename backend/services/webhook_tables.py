"""
Change D — DB migration for stateful webhook tables.

Uses ALTER TABLE ADD COLUMN IF NOT EXISTS so it's safe to run
against an existing DB that has the old tv_signals / orders /
account_snapshots schemas.
"""
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "stockradar"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
    )


_TV_SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS tv_signals (
    id              SERIAL PRIMARY KEY,
    strategy_id     VARCHAR(50),
    symbol          VARCHAR(10)  NOT NULL,
    target_position INTEGER      NOT NULL,
    actual_position INTEGER      NOT NULL DEFAULT 0,
    diff            INTEGER      NOT NULL DEFAULT 0,
    dedup_key       VARCHAR(100) UNIQUE,
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    ai_confidence   NUMERIC(5,2),
    executed_at     TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);
"""

# Columns added in Change D that the old schema is missing.
_TV_SIGNALS_MIGRATIONS = [
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS strategy_id     VARCHAR(50)",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS target_position INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS actual_position INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS diff            INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS dedup_key       VARCHAR(100)",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS ai_confidence   NUMERIC(5,2)",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS executed_at     TIMESTAMP",
    "ALTER TABLE tv_signals ADD COLUMN IF NOT EXISTS created_at      TIMESTAMP NOT NULL DEFAULT NOW()",
    # dedup_key must be unique — create index if not already a constraint
    """DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'tv_signals' AND indexname = 'tv_signals_dedup_key_key'
        ) THEN
            CREATE UNIQUE INDEX tv_signals_dedup_key_key ON tv_signals (dedup_key)
            WHERE dedup_key IS NOT NULL;
        END IF;
    END $$""",
]

_ORDERS_DDL = """
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    tv_signal_id    INTEGER REFERENCES tv_signals(id),
    symbol          VARCHAR(10)  NOT NULL,
    action          VARCHAR(10)  NOT NULL,
    quantity        INTEGER      NOT NULL,
    price           NUMERIC(12,2),
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    broker_order_id VARCHAR(50),
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);
"""

_ORDERS_MIGRATIONS = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS tv_signal_id    INTEGER REFERENCES tv_signals(id)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS broker_order_id VARCHAR(50)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at      TIMESTAMP NOT NULL DEFAULT NOW()",
]

_ACCOUNT_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS account_snapshots (
    id           SERIAL PRIMARY KEY,
    date         DATE         NOT NULL UNIQUE,
    total_value  NUMERIC(15,2) NOT NULL,
    cash         NUMERIC(15,2) NOT NULL,
    daily_pnl    NUMERIC(15,2) NOT NULL DEFAULT 0,
    margin_usage NUMERIC(5,4) NOT NULL DEFAULT 0,
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);
"""

_ACCOUNT_SNAPSHOTS_MIGRATIONS = [
    "ALTER TABLE account_snapshots ADD COLUMN IF NOT EXISTS total_value  NUMERIC(15,2) NOT NULL DEFAULT 0",
    "ALTER TABLE account_snapshots ADD COLUMN IF NOT EXISTS margin_usage NUMERIC(5,4)  NOT NULL DEFAULT 0",
    "ALTER TABLE account_snapshots ADD COLUMN IF NOT EXISTS created_at   TIMESTAMP     NOT NULL DEFAULT NOW()",
]


def ensure_tables() -> None:
    """Create Change D tables (or migrate existing ones)."""
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            # tv_signals
            cur.execute(_TV_SIGNALS_DDL)
            for stmt in _TV_SIGNALS_MIGRATIONS:
                cur.execute(stmt)

            # orders
            cur.execute(_ORDERS_DDL)
            for stmt in _ORDERS_MIGRATIONS:
                cur.execute(stmt)

            # account_snapshots
            cur.execute(_ACCOUNT_SNAPSHOTS_DDL)
            for stmt in _ACCOUNT_SNAPSHOTS_MIGRATIONS:
                cur.execute(stmt)

            conn.commit()
            logger.info("webhook_tables: Change D migration OK")
    except Exception as exc:
        logger.error("webhook_tables: migration failed — %s", exc)
