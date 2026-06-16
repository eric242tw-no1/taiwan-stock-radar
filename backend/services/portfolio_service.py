"""Portfolio service — persists holdings in SQLite portfolio table."""
import logging
from typing import Any

from db import get_conn

logger = logging.getLogger(__name__)


def ensure_table() -> None:
    pass  # schema managed by schema_sqlite.sql


def list_holdings() -> list[dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, qty, cost, buy_date, note, created_at FROM portfolio ORDER BY created_at")
        rows = [
            {**dict(r), "cost": float(r["cost"]), "buy_date": str(r["buy_date"]) if r["buy_date"] else ""}
            for r in cur.fetchall()
        ]
        conn.close()
        return rows
    except Exception as e:
        logger.error("list_holdings failed: %s", e)
        return []


def add_holding(code: str, name: str, qty: int, cost: float, buy_date: str | None, note: str) -> dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO portfolio (code, name, qty, cost, buy_date, note) VALUES (?, ?, ?, ?, ?, ?)",
        (code, name, qty, cost, buy_date or None, note),
    )
    row_id = cur.lastrowid
    cur.execute("SELECT id, code, name, qty, cost, buy_date, note FROM portfolio WHERE id=?", (row_id,))
    row = dict(cur.fetchone())
    conn.commit()
    conn.close()
    return {**row, "cost": float(row["cost"]), "buy_date": str(row["buy_date"]) if row["buy_date"] else ""}


def update_holding(holding_id: int, code: str, name: str, qty: int, cost: float, buy_date: str | None, note: str) -> dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE portfolio SET code=?, name=?, qty=?, cost=?, buy_date=?, note=? WHERE id=?",
        (code, name, qty, cost, buy_date or None, note, holding_id),
    )
    cur.execute("SELECT id, code, name, qty, cost, buy_date, note FROM portfolio WHERE id=?", (holding_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    if row is None:
        return None
    return {**dict(row), "cost": float(row["cost"]), "buy_date": str(row["buy_date"]) if row["buy_date"] else ""}


def delete_holding(holding_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM portfolio WHERE id=?", (holding_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0
