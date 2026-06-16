"""Trade Journal CRUD API."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()


class JournalEntry(BaseModel):
    symbol: str
    direction: str  # "buy" | "sell"
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    strategy: Optional[str] = None
    emotion: Optional[str] = None
    note: Optional[str] = None


def _row_to_dict(r) -> dict:
    return {
        "id": r[0], "symbol": r[1], "direction": r[2], "quantity": r[3],
        "entry_price": float(r[4]), "exit_price": float(r[5]) if r[5] is not None else None,
        "entry_at": str(r[6]), "exit_at": str(r[7]) if r[7] else None,
        "strategy": r[8], "emotion": r[9], "note": r[10], "created_at": str(r[11]),
    }


@router.get("/entries")
def list_entries(page: int = Query(1, ge=1), page_size: int = Query(20, le=100), symbol: Optional[str] = None):
    offset = (page - 1) * page_size
    conn = get_conn()
    cur = conn.cursor()
    if symbol:
        cur.execute("SELECT COUNT(*) FROM trade_journal WHERE symbol = ?", (symbol,))
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT id,symbol,direction,quantity,entry_price,exit_price,entry_at,exit_at,strategy,emotion,note,created_at "
            "FROM trade_journal WHERE symbol = ? ORDER BY entry_at DESC LIMIT ? OFFSET ?",
            (symbol, page_size, offset),
        )
    else:
        cur.execute("SELECT COUNT(*) FROM trade_journal")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT id,symbol,direction,quantity,entry_price,exit_price,entry_at,exit_at,strategy,emotion,note,created_at "
            "FROM trade_journal ORDER BY entry_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
    rows = cur.fetchall()
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "entries": [_row_to_dict(r) for r in rows]}


@router.post("/entries", status_code=201)
def create_entry(body: JournalEntry):
    if body.direction not in ("buy", "sell"):
        raise HTTPException(status_code=422, detail="direction 必須為 buy 或 sell")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO trade_journal (symbol,direction,quantity,entry_price,exit_price,strategy,emotion,note) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (body.symbol, body.direction, body.quantity, body.entry_price, body.exit_price,
         body.strategy, body.emotion, body.note),
    )
    row_id = cur.lastrowid
    cur.execute(
        "SELECT id,symbol,direction,quantity,entry_price,exit_price,entry_at,exit_at,strategy,emotion,note,created_at "
        "FROM trade_journal WHERE id=?", (row_id,)
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return _row_to_dict(row)


@router.put("/entries/{entry_id}")
def update_entry(entry_id: int, body: JournalEntry):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE trade_journal SET symbol=?,direction=?,quantity=?,entry_price=?,exit_price=?,"
        "strategy=?,emotion=?,note=? WHERE id=?",
        (body.symbol, body.direction, body.quantity, body.entry_price, body.exit_price,
         body.strategy, body.emotion, body.note, entry_id),
    )
    cur.execute(
        "SELECT id,symbol,direction,quantity,entry_price,exit_price,entry_at,exit_at,strategy,emotion,note,created_at "
        "FROM trade_journal WHERE id=?", (entry_id,)
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="記錄不存在")
    return _row_to_dict(row)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM trade_journal WHERE id=?", (entry_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="記錄不存在")


@router.get("/stats")
def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(exit_price) AS closed,
            SUM(CASE WHEN exit_price > entry_price AND direction='buy' THEN 1
                     WHEN exit_price < entry_price AND direction='sell' THEN 1
                     ELSE 0 END) AS wins,
            AVG(CASE WHEN exit_price IS NOT NULL THEN
                (exit_price - entry_price) * CASE WHEN direction='buy' THEN 1 ELSE -1 END
            END) AS avg_pnl,
            emotion, COUNT(*) AS cnt
        FROM trade_journal
        GROUP BY emotion
    """)
    rows = cur.fetchall()
    conn.close()

    total = sum(r[0] for r in rows)
    closed = sum(r[1] for r in rows)
    wins = sum(r[2] or 0 for r in rows)
    avg_pnl = sum((r[3] or 0) * r[0] for r in rows) / total if total else 0
    win_rate = wins / closed if closed else 0

    emotion_dist = [{"emotion": r[4] or "未記錄", "count": r[5]} for r in rows]

    return {
        "total": total, "closed": closed, "win_rate": round(win_rate, 4),
        "avg_pnl": round(float(avg_pnl), 2), "emotion_distribution": emotion_dist,
    }
