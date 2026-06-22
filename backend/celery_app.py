"""Celery application — broker and result backend both use the existing Redis instance."""
import os

from celery import Celery

_redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "taiwan_stock_radar",
    broker=_redis_url,
    backend=_redis_url,
    include=["celery_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=False,
    worker_prefetch_multiplier=1,
)
