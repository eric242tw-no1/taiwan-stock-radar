"""任務監控 API — 列出 APScheduler 排程任務（取代已移除的 Celery/Flower）。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/jobs")
def list_jobs():
    """回傳所有排程任務的 id、觸發規則與下次執行時間。"""
    from main import scheduler

    jobs = []
    for j in scheduler.get_jobs():
        jobs.append({
            "id": j.id,
            "trigger": str(j.trigger),
            "next_run": j.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if j.next_run_time else None,
        })
    jobs.sort(key=lambda x: x["next_run"] or "9999")
    return {"count": len(jobs), "running": scheduler.running, "jobs": jobs}
