"""AES-256-GCM for BYOK provider keys, plus HMAC token signing.

The master key lives ONLY in the environment (Lambda config). We store
`"{iv}.{ciphertext}.{tag}"` base64url segments so the whole thing fits a
String(1024) column and round-trips as plain text. GCM gives us
authenticated encryption — a tampered ciphertext fails to decrypt rather
than silently returning garbage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _master_key() -> bytes:
    """Derive a stable 32-byte key from the configured secret.

    We SHA-256 the configured value so any-length env string yields a valid
    256-bit key. In prod, set ENCRYPTION_KEY to a high-entropy secret.
    """
    return hashlib.sha256(settings.encryption_key.encode()).digest()


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encrypt(plaintext: str) -> str:
    """Encrypt a secret (e.g. a provider API key) for storage at rest."""
    aes = AESGCM(_master_key())
    iv = os.urandom(12)  # fresh 96-bit random nonce per encryption — GCM requires this
    ct = aes.encrypt(iv, plaintext.encode(), None)  # returns ciphertext||tag
    return f"{_b64e(iv)}.{_b64e(ct)}"


def decrypt(token: str) -> str:
    """Reverse of `encrypt`. Raises on tampering (GCM auth failure)."""
    iv_b64, ct_b64 = token.split(".", 1)
    aes = AESGCM(_master_key())
    pt = aes.decrypt(_b64d(iv_b64), _b64d(ct_b64), None)
    return pt.decode()


# ── HMAC-signed opaque tokens (unsubscribe links, etc.) ───────────────────
# Format: "{payload}.{sig}" where sig = HMAC-SHA256(payload). Constant-time
# compared on verify — same discipline as the GitHub webhook check.


def sign(payload: str) -> str:
    sig = hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256)
    return f"{payload}.{_b64e(sig.digest())}"


def verify_signed(token: str) -> str | None:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256)
    if hmac.compare_digest(_b64d(sig), expected.digest()):
        return payload
    return None


def sha256_hex(raw: str) -> str:
    """Hash an API key for storage (raw shown once, only hash persisted)."""
    return hashlib.sha256(raw.encode()).hexdigest()
