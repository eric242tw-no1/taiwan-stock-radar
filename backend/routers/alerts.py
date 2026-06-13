"""
警報規則 CRUD API
GET    /api/alerts          — 列出所有規則
POST   /api/alerts          — 新增規則
DELETE /api/alerts/{id}     — 刪除規則
POST   /api/alerts/test     — 發送測試訊息

持久化：後端 data/alerts.json，重啟後資料不消失。
"""
import json
import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional
from utils.telegram import send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# ── 持久化路徑 ─────────────────────────────────────────────────
_DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
_ALERTS_FILE = os.path.join(_DATA_DIR, "alerts.json")

# ── in-memory store ────────────────────────────────────────────
_rules: dict[int, dict] = {}
_next_id = 1


def _load() -> None:
    """從 JSON 檔案載入規則到記憶體（後端啟動時呼叫）。"""
    global _rules, _next_id
    os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.exists(_ALERTS_FILE):
        return
    try:
        with open(_ALERTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _rules   = {int(k): v for k, v in data.get("rules", {}).items()}
        _next_id = data.get("next_id", 1)
        logger.info("alerts: loaded %d rules from %s", len(_rules), _ALERTS_FILE)
    except Exception as e:
        logger.warning("alerts: failed to load %s — %s", _ALERTS_FILE, e)


def _save() -> None:
    """把記憶體中的規則寫入 JSON 檔案。"""
    os.makedirs(_DATA_DIR, exist_ok=True)
    try:
        with open(_ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"rules": _rules, "next_id": _next_id}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("alerts: failed to save %s — %s", _ALERTS_FILE, e)


# 載入已儲存的規則
_load()


class AlertRule(BaseModel):
    symbol: str
    name: Optional[str] = ""
    type: Literal["price", "rsi", "volume", "ai_score", "deviation", "change_pct", "limit", "large_order", "both"] = "both"
    threshold: Optional[float] = None
    operator: Optional[str] = "gte"       # gte | lte | gt | lt
    large_order_threshold: Optional[int] = 500  # 張
    enabled: Optional[bool] = True


class TestMessage(BaseModel):
    text: str


@router.get("")
def list_rules():
    return list(_rules.values())


@router.post("", status_code=201)
def create_rule(body: AlertRule):
    global _next_id
    rule = {"id": _next_id, **body.model_dump()}
    _rules[_next_id] = rule
    _next_id += 1
    _save()
    return rule


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: AlertRule):
    if rule_id not in _rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    _rules[rule_id] = {"id": rule_id, **body.model_dump()}
    _save()
    return _rules[rule_id]


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    if rule_id not in _rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    del _rules[rule_id]
    _save()


@router.post("/test")
async def test_alert(body: TestMessage):
    ok = await send_message(body.text)
    if not ok:
        raise HTTPException(status_code=503, detail="Telegram 發送失敗，請確認 BOT_TOKEN / CHAT_ID")
    return {"status": "sent"}


def get_watchlist() -> list[dict]:
    """提供給 alert_agent 使用的監控清單。"""
    return [{"symbol": r["symbol"], "name": r["name"]} for r in _rules.values()]
