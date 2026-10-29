"""Password hashing (scrypt), signed auth tokens (HMAC-SHA256) and opaque public tokens."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import get_settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict, ttl_seconds: int) -> str:
    body = dict(payload, exp=int(time.time()) + ttl_seconds)
    raw = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = hmac.new(get_settings().secret_key.encode(), raw.encode(), hashlib.sha256).digest()
    return f"{raw}.{_b64(sig)}"


def read_token(token: str) -> dict | None:
    try:
        raw, sig = token.split(".")
        expected = hmac.new(get_settings().secret_key.encode(), raw.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig)):
            return None
        body = json.loads(_unb64(raw))
        return body if body.get("exp", 0) >= time.time() else None
    except Exception:
        return None


def public_token(nbytes: int = 24) -> str:
    """Unguessable URL-safe token for table sessions, QR codes and receipts."""
    return secrets.token_urlsafe(nbytes)
