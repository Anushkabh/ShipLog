"""Email subscribers with double opt-in + HMAC-signed unsubscribe (§8).

Subscribe is public (widget/site). We create an unverified row + verify token
and email a confirmation link; only verified subscribers receive broadcasts.
Unsubscribe uses an HMAC-signed token so nobody can unsubscribe someone else by
guessing an id.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import DbDep
from app.models import Project, Subscriber
from app.schemas import SubscribeRequest
from app.services import crypto
from app.services.email import send_email

router = APIRouter(prefix="/api/v1/widget", tags=["subscribers"])


@router.post("/{public_key}/subscribe", status_code=status.HTTP_202_ACCEPTED)
async def subscribe(public_key: str, body: SubscribeRequest, db: DbDep) -> dict:
    project = await db.scalar(select(Project).where(Project.public_key == public_key))
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown project")

    existing = await db.scalar(
        select(Subscriber).where(
            Subscriber.project_id == project.id, Subscriber.email == body.email
        )
    )
    if existing and existing.verified:
        return {"status": "already_subscribed"}

    sub = existing or Subscriber(project_id=project.id, email=body.email)
    sub.verify_token = secrets.token_urlsafe(24)
    if not existing:
        db.add(sub)
    await db.commit()

    from app.config import settings

    link = f"{settings.api_url}/api/v1/widget/{public_key}/verify/{sub.verify_token}"
    html = (
        f"<p>Confirm to get {project.name} updates:</p>"
        f'<p><a href="{link}">Confirm subscription</a></p>'
    )
    await send_email(
        to=body.email,
        subject=f"Confirm your subscription to {project.name}",
        html=html,
    )
    return {"status": "verification_sent"}


@router.get("/{public_key}/verify/{token}")
async def verify(public_key: str, token: str, db: DbDep) -> Response:
    sub = await db.scalar(select(Subscriber).where(Subscriber.verify_token == token))
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid or used link")
    sub.verified = True
    sub.verify_token = None
    await db.commit()
    return Response("Subscription confirmed. You're all set!", media_type="text/plain")


@router.get("/unsubscribe/{signed}")
async def unsubscribe(signed: str, db: DbDep) -> Response:
    # `signed` = crypto.sign(unsub_token); verify HMAC before touching the row.
    unsub_token = crypto.verify_signed(signed)
    if not unsub_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid unsubscribe link")
    sub = await db.scalar(select(Subscriber).where(Subscriber.unsub_token == unsub_token))
    if sub:
        await db.delete(sub)
        await db.commit()
    return Response("You've been unsubscribed.", media_type="text/plain")
