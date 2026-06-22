"""通知中心 API"""
from fastapi import APIRouter, Query, HTTPException
from db import get_conn

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
):
    """取得通知列表，依 created_at 降冪排序。"""
    conn = get_conn()
    where = "WHERE is_read = 0" if unread_only else ""
    rows = conn.execute(
        f"SELECT id, message, source, created_at, is_read FROM notifications "
        f"{where} ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    total_unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE is_read = 0"
    ).fetchone()[0]
    conn.close()
    return {
        "total_unread": total_unread,
        "count": len(rows),
        "notifications": [
            {"id": r[0], "message": r[1], "source": r[2], "created_at": r[3], "is_read": bool(r[4])}
            for r in rows
        ],
    }


@router.patch("/{nid}/read")
async def mark_read(nid: int):
    """標記單筆通知為已讀。"""
    conn = get_conn()
    result = conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ?", (nid,)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="notification not found")
    return {"ok": True}


@router.patch("/read-all")
async def mark_all_read():
    """標記所有未讀通知為已讀。"""
    conn = get_conn()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
    conn.commit()
    conn.close()
    return {"ok": True}
