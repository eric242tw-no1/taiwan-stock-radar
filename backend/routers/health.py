import os
import subprocess

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db import get_conn

router = APIRouter()


@router.get("/health")
async def health_check():
    result = {"status": "ok", "db": "ok", "redis": "ok", "version": _git_sha()}
    status_code = 200

    # Check SQLite
    try:
        conn = get_conn()
        conn.execute("SELECT 1")
        conn.close()
    except Exception as e:
        result["db"] = f"error: {e}"
        result["status"] = "degraded"
        status_code = 503

    # Check Redis（REDIS_URL 未設定＝單機模式，快取走 SQLite，不算 degraded）
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        result["redis"] = "disabled"
    else:
        try:
            r = aioredis.from_url(redis_url, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
        except Exception as e:
            result["redis"] = f"error: {e}"
            result["status"] = "degraded"
            status_code = 503

    return JSONResponse(content=result, status_code=status_code)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"
