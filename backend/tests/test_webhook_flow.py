"""
Integration test: full stateful webhook flow (HMAC → dedup → diff → AI → order)
Uses monkeypatching — no real DB / Redis / broker required.
"""

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret"
PAYLOAD = {
    "strategy_id": "swing_v1",
    "symbol": "2330",
    "secret": SECRET,
    "target_position": 1000,
    "timestamp": 1718000000,
}


def _make_app():
    """Build a minimal FastAPI app with the webhook router."""
    from fastapi import FastAPI
    from routers.webhook import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TV_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

    # Stub DB writes
    monkeypatch.setattr("routers.webhook._insert_tv_signal", lambda **kw: 1)
    monkeypatch.setattr("routers.webhook._update_tv_signal", lambda *a, **kw: None)
    monkeypatch.setattr("routers.webhook._insert_order", lambda *a, **kw: None)

    # Stub dedup (no dedup)
    monkeypatch.setattr("routers.webhook._is_duplicate", lambda key: False)

    # Stub broker（webhook 於 handler 內 `from scheduler_tasks import _broker`，需 patch scheduler_tasks）
    import asyncio

    async def _fake_get_position(symbol):
        return 0

    async def _fake_place_order(**kw):
        return {"order_id": "FAKE-001"}

    class FakeBroker:
        get_position = staticmethod(_fake_get_position)
        place_order = staticmethod(_fake_place_order)

    monkeypatch.setattr("scheduler_tasks._broker", FakeBroker(), raising=False)

    # Stub Telegram 下單確認（立即視為已確認，跳過 60 秒等待）
    _confirmed = asyncio.Event()
    _confirmed.set()
    monkeypatch.setattr("utils.telegram_bot.register_pending", lambda sid: _confirmed)
    monkeypatch.setattr("utils.telegram_bot.is_confirmed", lambda sid: True)

    async def _noop_confirm(**kw):
        pass

    monkeypatch.setattr("utils.telegram.send_order_confirm", _noop_confirm)

    # Stub AI
    async def _fake_devil_advocate(*a, **kw):
        return {"confidence": 0.85, "approved": True, "reason": "測試通過"}

    monkeypatch.setattr("agents.ai_engine.devil_advocate", _fake_devil_advocate)

    # Stub telegram
    async def _noop(*a, **kw): pass
    monkeypatch.setattr("routers.webhook.send_message", _noop)

    return TestClient(_make_app())


def test_wrong_secret_returns_403(client, monkeypatch):
    bad = {**PAYLOAD, "secret": "wrong"}
    r = client.post("/api/webhook/tradingview", json=bad)
    assert r.status_code == 403


def test_missing_field_returns_422(client):
    bad = {k: v for k, v in PAYLOAD.items() if k != "target_position"}
    r = client.post("/api/webhook/tradingview", json=bad)
    assert r.status_code == 422


def test_successful_flow(client, monkeypatch):
    # Patch devil_advocate inside the router module
    def _approved(*a, **kw):
        return {"confidence": 0.9, "approved": True, "reason": "OK"}

    monkeypatch.setattr("agents.ai_engine.devil_advocate", _approved)
    
    def _get_pos(symbol): return 0

    def _place(**kw): return {"order_id": "X1"}

    monkeypatch.setattr("main._broker", type("B", (), {
        "get_position": staticmethod(_get_pos),
        "place_order": staticmethod(_place),
    })())

    r = client.post("/api/webhook/tradingview", json=PAYLOAD)
    # either submitted or error depending on async stubs — just not 4xx
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "2330"
    assert body["action"] == "buy"


def test_ai_rejection(client, monkeypatch):
    async def _rejected(*a, **kw):
        return {"confidence": 0.3, "approved": False, "reason": "風險過高"}

    async def _get_pos(symbol): return 0
    monkeypatch.setattr("agents.ai_engine.devil_advocate", _rejected)
    monkeypatch.setattr("main._broker", type("B", (), {"get_position": staticmethod(_get_pos)})())

    r = client.post("/api/webhook/tradingview", json=PAYLOAD)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_no_change_when_diff_zero(client, monkeypatch):
    async def _same_pos(symbol): return PAYLOAD["target_position"]
    monkeypatch.setattr("main._broker", type("B", (), {"get_position": staticmethod(_same_pos)})())

    r = client.post("/api/webhook/tradingview", json=PAYLOAD)
    assert r.status_code == 200
    assert r.json()["status"] == "no_change"
