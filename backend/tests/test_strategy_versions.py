"""策略版本化 API 測試：驗證 active 唯一性約束與 CRUD 流程。"""
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_version(strategy_id: int, version: str) -> dict:
    return {
        "strategy_id": strategy_id,
        "version": version,
        "prompt_template": f"Prompt for {version}",
        "parameters": {"weight": 0.5},
    }


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.strategies import router
    app = FastAPI()
    app.include_router(router)

    # Mock DB calls
    _db: list[dict] = []
    _id_counter = {"n": 0}

    def _fake_list(strategy_id=None):
        rows = _db if strategy_id is None else [v for v in _db if v["strategy_id"] == strategy_id]
        return {"versions": rows}

    def _fake_create(body):
        _id_counter["n"] += 1
        row = {
            "id": _id_counter["n"],
            "strategy_id": body.strategy_id,
            "version": body.version,
            "parameters": body.parameters,
            "is_active": False,
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        _db.append(row)
        return row

    def _fake_activate(version_id: int):
        target = next((v for v in _db if v["id"] == version_id), None)
        if not target:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="版本不存在")
        sid = target["strategy_id"]
        for v in _db:
            if v["strategy_id"] == sid:
                v["is_active"] = False
        target["is_active"] = True
        return {"activated": version_id, "strategy_id": sid}

    import routers.strategies as mod
    monkeypatch.setattr(mod, "list_versions", _fake_list)
    monkeypatch.setattr(mod, "create_version", _fake_create)
    monkeypatch.setattr(mod, "activate_version", _fake_activate)

    return TestClient(app), _db


# ── tests ────────────────────────────────────────────────────────────────────

def test_create_version(client):
    c, db = client
    r = c.post("/api/strategies/versions", json=_make_version(1, "v1.0"))
    assert r.status_code == 201
    body = r.json()
    assert body["version"] == "v1.0"
    assert body["is_active"] is False


def test_list_versions(client):
    c, db = client
    c.post("/api/strategies/versions", json=_make_version(1, "v1.0"))
    c.post("/api/strategies/versions", json=_make_version(1, "v1.1"))
    c.post("/api/strategies/versions", json=_make_version(2, "v2.0"))

    r = c.get("/api/strategies/versions?strategy_id=1")
    assert r.status_code == 200
    assert len(r.json()["versions"]) == 2


def test_activate_ensures_uniqueness(client):
    """啟用新版本後，同 strategy_id 的舊版本應自動停用。"""
    c, db = client
    r1 = c.post("/api/strategies/versions", json=_make_version(1, "v1.0"))
    r2 = c.post("/api/strategies/versions", json=_make_version(1, "v1.1"))
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    c.get(f"/api/strategies/versions/{id1}/activate")
    assert next(v for v in db if v["id"] == id1)["is_active"] is True

    # 啟用 v1.1，v1.0 應停用
    c.get(f"/api/strategies/versions/{id2}/activate")
    assert next(v for v in db if v["id"] == id1)["is_active"] is False
    assert next(v for v in db if v["id"] == id2)["is_active"] is True


def test_activate_nonexistent_returns_404(client):
    c, _ = client
    r = c.get("/api/strategies/versions/9999/activate")
    assert r.status_code == 404
