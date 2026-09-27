"""Which AI key a project uses — its own (BYOK) or the built-in platform key.

Users shouldn't need an API key to try the product, so the platform key is the
default. A project that saves its own key uses that instead (no daily cap —
it's their quota). Every AI entry point resolves access here so the rule lives
in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select

from app.config import settings
from app.models import AiCredential, AiProvider, Project
from app.services import cache, crypto


@dataclass
class AiAccess:
    provider: AiProvider
    api_key: str
    source: str  # "project" | "platform"


def platform_available() -> bool:
    return bool(settings.platform_ai_api_key)


async def resolve(db, project: Project) -> AiAccess | None:
    """The project's own key if it has one, else the platform key, else None."""
    cred = await db.scalar(
        select(AiCredential).where(AiCredential.project_id == project.id)
    )
    if cred:
        return AiAccess(cred.provider, crypto.decrypt(cred.encrypted_key), "project")
    if platform_available():
        return AiAccess(
            AiProvider(settings.platform_ai_provider),
            settings.platform_ai_api_key,
            "platform",
        )
    return None


async def require(db, project: Project) -> AiAccess:
    """Resolve access and charge the platform daily quota. Raises HTTP errors
    the dashboard shows verbatim."""
    access = await resolve(db, project)
    if access is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "AI drafting isn't available yet — add your own provider key on the AI page.",
        )
    if access.source == "platform":
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        allowed = await cache.rate_limit(
            f"ai:{project.id}:{day}", settings.platform_ai_daily_limit, 86_400
        )
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Daily limit of {settings.platform_ai_daily_limit} AI drafts reached "
                "for this project. Add your own key on the AI page for unlimited use.",
            )
    return access
