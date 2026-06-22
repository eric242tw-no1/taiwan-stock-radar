"""Task status API — GET /api/tasks/{task_id}/status"""
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}/status")
def get_task_status(task_id: str):
    """Query Celery task status by task_id."""
    from celery_app import app as celery_app
    result = AsyncResult(task_id, app=celery_app)
    response: dict = {"task_id": task_id, "status": result.state}
    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info)
    return response
