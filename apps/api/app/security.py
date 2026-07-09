"""Session tokens: short JWTs carried in an httpOnly, SameSite=Lax cookie.

Never localStorage (ARCHITECTURE §9). Because Next.js proxies /api/* to this
Lambda, the cookie is first-party — no cross-site cookie pain, reduced CSRF
surface. The cookie is issued after the GitHub OAuth dance (see routers/auth).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings

COOKIE_NAME = "shiplog_session"
_ALG = "HS256"


def issue_session(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def read_session(token: str) -> str | None:
    """Return the user_id from a valid token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALG])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        secure=settings.is_prod,          # Secure everywhere except local http
        samesite="lax",
        domain=settings.cookie_domain,     # None locally; .shiplog.app in prod
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(
        COOKIE_NAME, domain=settings.cookie_domain, path="/"
    )
