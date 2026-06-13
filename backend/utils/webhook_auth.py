import hashlib
import hmac
import os


def verify_hmac(body: bytes, signature: str) -> bool:
    """Return True if signature matches HMAC-SHA256(TV_WEBHOOK_SECRET, body).

    TradingView sends the hex digest in the X-Webhook-Signature header.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    secret = os.getenv("TV_WEBHOOK_SECRET", "")
    if not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
