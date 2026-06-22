"""多空辯論 API 格式驗證測試。"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_msg(text: str) -> MagicMock:
    content = MagicMock()
    content.text = text
    msg = MagicMock()
    msg.content = [content]
    return msg


BULL_ARGS = json.dumps([
    {"title": "強勁業績", "argument": "連續三季超預期。AI 需求旺盛。", "evidence": "EPS +30%"},
    {"title": "法人買超", "argument": "外資連買 5 日。投信加碼。", "evidence": "外資+2000張"},
    {"title": "技術突破", "argument": "突破 MA20。MACD 翻正。", "evidence": "RSI=62"},
])
BEAR_ARGS = json.dumps([
    {"title": "估值過高", "argument": "PE 超過 25 倍。超買風險。", "evidence": "PE=26"},
    {"title": "匯率逆風", "argument": "台幣升值壓縮毛利。出口競爭力下降。", "evidence": "USD/TWD=30"},
    {"title": "同業競爭", "argument": "Samsung 擴產。市佔率風險。", "evidence": "Samsung CapEx +20%"},
])
ARBITER = json.dumps({
    "verdict": "bull",
    "confidence": 72,
    "rationale": "多方論點較為有力。基本面支撐估值。技術面看多。",
    "key_risk": "美中貿易摩擦可能衝擊供應鏈。",
})


@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from routers.analysis import router
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_debate_response_structure(client, monkeypatch):
    """驗證 debate API 回應包含必要欄位。"""
    import routers.analysis as mod

    async def _fake_bull(*args, **kwargs):
        return json.loads(BULL_ARGS)

    async def _fake_bear(*args, **kwargs):
        return json.loads(BEAR_ARGS)

    async def _fake_arbiter(*args, **kwargs):
        return json.loads(ARBITER)

    monkeypatch.setattr(mod, "_run_bull_agent", _fake_bull)
    monkeypatch.setattr(mod, "_run_bear_agent", _fake_bear)
    monkeypatch.setattr(mod, "_run_arbiter", _fake_arbiter)
    monkeypatch.setattr(mod, "_get_price_context", lambda s: "收盤價 850")

    r = client.post("/api/analysis/debate/2330", json={})
    assert r.status_code == 200

    body = r.json()
    assert body["symbol"] == "2330"
    assert "timestamp" in body
    assert len(body["bull_arguments"]) == 3
    assert len(body["bear_arguments"]) == 3

    bull = body["bull_arguments"][0]
    assert "title" in bull and "argument" in bull and "evidence" in bull

    arbiter = body["arbiter"]
    assert arbiter["verdict"] in ("bull", "bear", "neutral")
    assert 60 <= arbiter["confidence"] <= 100
    assert "rationale" in arbiter
    assert "key_risk" in arbiter


def test_debate_invalid_symbol(client):
    r = client.post("/api/analysis/debate/TSMC", json={})
    assert r.status_code == 400
