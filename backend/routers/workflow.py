"""Workflow definitions CRUD API."""
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()


class WorkflowSaveRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


@router.get("/list")
def list_workflows():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description, created_at, updated_at FROM workflow_definitions ORDER BY updated_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return {
        "workflows": [
            {"id": r[0], "name": r[1], "description": r[2], "created_at": str(r[3]), "updated_at": str(r[4])}
            for r in rows
        ]
    }


@router.post("/save", status_code=201)
def save_workflow(body: WorkflowSaveRequest):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO workflow_definitions (name, description, nodes_json, edges_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (body.name, body.description, json.dumps(body.nodes), json.dumps(body.edges)),
        )
        row_id = cur.lastrowid
        cur.execute("SELECT id, created_at, updated_at FROM workflow_definitions WHERE id=?", (row_id,))
        row = cur.fetchone()
        conn.commit()
        conn.close()
        return {"id": row[0], "name": body.name, "created_at": str(row[1]), "updated_at": str(row[2])}
    except Exception as exc:
        logger.error("save_workflow error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run/{workflow_id}")
def run_workflow(workflow_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM workflow_definitions WHERE id = ?", (workflow_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="工作流程不存在")
    return {"workflow_id": workflow_id, "status": "queued", "message": f"工作流程「{row[1]}」已加入執行佇列"}
