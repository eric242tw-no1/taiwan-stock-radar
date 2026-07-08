"""
策略版本化 API (Change A)

GET  /api/strategies                        — 列出策略（供版本管理頁下拉）
GET  /api/strategies/versions              — 列出版本（可篩選 strategy_id）
POST /api/strategies/versions              — 建立新版本
GET  /api/strategies/versions/{id}/activate — 啟用特定版本（同 strategy_id 的其他版本停用）

active 版本的 prompt_template 由 agents/multi_agent_engine._load_active_prompt()
以 strategies.name 對應 agent 套用於 AI 分析。
"""
import json
import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class VersionIn(BaseModel):
    strategy_id: int
    version: str
    prompt_template: str
    parameters: dict = {}


@router.get("")
def list_strategies():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, name, mode, is_active FROM strategies ORDER BY id"
    ).fetchall()]
    conn.close()
    return {"strategies": rows}


@router.get("/versions")
def list_versions(strategy_id: int | None = Query(None)):
    try:
        conn = get_conn()
        cur = conn.cursor()
        base = (
            "SELECT sv.id, sv.strategy_id, s.name AS strategy_name, sv.version, "
            "sv.prompt_template, sv.parameters, sv.is_active, sv.created_at "
            "FROM strategy_versions sv JOIN strategies s ON s.id = sv.strategy_id "
        )
        if strategy_id is not None:
            cur.execute(base + "WHERE sv.strategy_id=? ORDER BY sv.created_at DESC", (strategy_id,))
        else:
            cur.execute(base + "ORDER BY sv.created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"versions": rows}
    except Exception as exc:
        logger.error("list_versions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/versions", status_code=201)
def create_version(body: VersionIn):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO strategy_versions (strategy_id, version, prompt_template, parameters) "
            "VALUES (?, ?, ?, ?)",
            (body.strategy_id, body.version, body.prompt_template, json.dumps(body.parameters)),
        )
        row_id = cur.lastrowid
        cur.execute(
            "SELECT id, strategy_id, version, parameters, is_active, created_at "
            "FROM strategy_versions WHERE id=?", (row_id,)
        )
        row = dict(cur.fetchone())
        conn.commit()
        conn.close()
        return row
    except sqlite3.IntegrityError as exc:
        if "FOREIGN KEY" in str(exc).upper():
            raise HTTPException(status_code=404, detail="strategy_id 不存在")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("create_version failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/versions/{version_id}/activate")
def activate_version(version_id: int):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT strategy_id FROM strategy_versions WHERE id=?", (version_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="版本不存在")
        strategy_id = row[0]
        cur.execute("UPDATE strategy_versions SET is_active=0 WHERE strategy_id=?", (strategy_id,))
        cur.execute("UPDATE strategy_versions SET is_active=1 WHERE id=?", (version_id,))
        conn.commit()
        conn.close()
        return {"activated": version_id, "strategy_id": strategy_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("activate_version failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
