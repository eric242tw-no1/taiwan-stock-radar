"""Reports API — GET /api/reports/morning-brief"""
import json
import logging
from datetime import date

from fastapi import APIRouter, HTTPException

from db import get_conn

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.get("/morning-brief")
def get_morning_brief(report_date: date | None = None):
    target = report_date or date.today()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT date, report_json, sent_at FROM daily_ai_report WHERE date = ?",
            (str(target),),
        )
        row = cur.fetchone()
        conn.close()
    except Exception as exc:
        logger.error("reports: DB error — %s", exc)
        raise HTTPException(status_code=500, detail="DB error")

    if not row:
        raise HTTPException(status_code=404, detail=f"No morning brief for {target}")

    report_json = json.loads(row[1]) if isinstance(row[1], str) else row[1]
    return {"date": str(row[0]), "report": report_json, "sent_at": row[2]}
