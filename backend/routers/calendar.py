"""財報日曆 API — GET /api/calendar/events"""
from fastapi import APIRouter, Query
from services.earnings_calendar import get_events, fetch_and_store_calendar

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/events")
async def get_calendar_events(days: int = Query(default=30, ge=1, le=90)):
    """回傳未來 N 天的除息/除權/法說/財報日曆事件。"""
    events = get_events(days)
    return {"days": days, "count": len(events), "events": events}


@router.post("/refresh")
async def refresh_calendar(days: int = Query(default=30, ge=1, le=90)):
    """手動觸發財報日曆更新（忽略 TTL）。"""
    count = fetch_and_store_calendar(days)
    return {"refreshed": count}
