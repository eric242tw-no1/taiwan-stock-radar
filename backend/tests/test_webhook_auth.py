import hashlib
import hmac


from utils.webhook_auth import verify_hmac


SECRET = "test-secret-key"
BODY = b'{"strategy_id":"s1","symbol":"2330","target_position":1000}'


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_correct_secret_passes(monkeypatch):
    monkeypatch.setenv("TV_WEBHOOK_SECRET", SECRET)
    sig = _sign(BODY, SECRET)
    assert verify_hmac(BODY, sig) is True


def test_wrong_secret_fails(monkeypatch):
    monkeypatch.setenv("TV_WEBHOOK_SECRET", SECRET)
    sig = _sign(BODY, "wrong-secret")
    assert verify_hmac(BODY, sig) is False


def test_missing_secret_fails(monkeypatch):
    monkeypatch.delenv("TV_WEBHOOK_SECRET", raising=False)
    sig = _sign(BODY, SECRET)
    assert verify_hmac(BODY, sig) is False


def test_tampered_body_fails(monkeypatch):
    monkeypatch.setenv("TV_WEBHOOK_SECRET", SECRET)
    sig = _sign(BODY, SECRET)
    tampered = BODY + b"extra"
    assert verify_hmac(tampered, sig) is False
