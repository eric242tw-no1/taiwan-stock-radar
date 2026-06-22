"""AI Self Audit API — GET /api/audit/accuracy"""
from fastapi import APIRouter, Query
from services.audit import get_accuracy_report

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/accuracy")
async def get_accuracy(days: int = Query(default=30, ge=1, le=365)):
    """
    AI 預測準確率報表（最近 N 天）
    回傳：total / correct / accuracy% / by_symbol / recent 20 筆
    """
    return get_accuracy_report(days)
