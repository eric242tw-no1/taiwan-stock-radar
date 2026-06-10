"""
Portfolio service — persists holdings in PostgreSQL portfolio table.
"""
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


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
    CREATE TABLE IF NOT EXISTS portfolio (
        id         SERIAL PRIMARY KEY,
        code       VARCHAR(16) NOT NULL,
        name       VARCHAR(64) NOT NULL DEFAULT '',
        qty        INTEGER     NOT NULL,
        cost       NUMERIC(10, 2) NOT NULL,
        buy_date   DATE,
        note       TEXT        NOT NULL DEFAULT '',
        created_at TIMESTAMP   NOT NULL DEFAULT NOW()
    );
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()
        logger.info("portfolio table ready")
    except Exception as e:
        logger.error("portfolio ensure_table failed: %s", e)


def list_holdings() -> list[dict[str, Any]]:
    sql = "SELECT id, code, name, qty, cost, buy_date, note, created_at FROM portfolio ORDER BY created_at"
    try:
        with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {**dict(r), "cost": float(r["cost"]), "buy_date": str(r["buy_date"]) if r["buy_date"] else ""}
                for r in rows
            ]
    except Exception as e:
        logger.error("list_holdings failed: %s", e)
        return []


def add_holding(code: str, name: str, qty: int, cost: float, buy_date: str | None, note: str) -> dict[str, Any]:
    sql = """
        INSERT INTO portfolio (code, name, qty, cost, buy_date, note)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, code, name, qty, cost, buy_date, note
    """
    with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (code, name, qty, cost, buy_date or None, note))
        row = dict(cur.fetchone())
        conn.commit()
    return {**row, "cost": float(row["cost"]), "buy_date": str(row["buy_date"]) if row["buy_date"] else ""}


def update_holding(holding_id: int, code: str, name: str, qty: int, cost: float, buy_date: str | None, note: str) -> dict[str, Any] | None:
    sql = """
        UPDATE portfolio
        SET code=%s, name=%s, qty=%s, cost=%s, buy_date=%s, note=%s
        WHERE id=%s
        RETURNING id, code, name, qty, cost, buy_date, note
    """
    with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (code, name, qty, cost, buy_date or None, note, holding_id))
        row = cur.fetchone()
        conn.commit()
    if row is None:
        return None
    return {**dict(row), "cost": float(row["cost"]), "buy_date": str(row["buy_date"]) if row["buy_date"] else ""}


def delete_holding(holding_id: int) -> bool:
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM portfolio WHERE id=%s", (holding_id,))
        deleted = cur.rowcount
        conn.commit()
    return deleted > 0
