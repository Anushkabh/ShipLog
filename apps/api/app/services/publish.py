"""The publish transaction (ARCHITECTURE §8), shared by the manual publish
route and the EventBridge scheduler so the logic exists exactly once.

Steps:
  1. status -> published, stamp published_at (idempotent: no-op if already live)
  2. bust the widget feed cache key in Redis
  3. tell Next.js to revalidate the tenant's static pages (on-demand ISR)
  4. if broadcasting, enqueue an email fan-out job (batched downstream)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import EmailBroadcast, Project, Release, ReleaseStatus
from app.services import cache
from app.services.queue import Queue, enqueue

log = logging.getLogger("shiplog.publish")


async def publish_release(
    db: AsyncSession,
    project: Project,
    release: Release,
    *,
    broadcast_email: bool = True,
) -> None:
    already_live = release.status == ReleaseStatus.PUBLISHED

    release.status = ReleaseStatus.PUBLISHED
    if release.published_at is None:
        release.published_at = datetime.now(UTC)
    release.scheduled_at = None

    broadcast_id: str | None = None
    if broadcast_email and not already_live and project.email_enabled:
        broadcast = EmailBroadcast(release_id=release.id)
        db.add(broadcast)
        await db.flush()
        broadcast_id = broadcast.id

    await db.commit()

    # Side effects AFTER the DB is durable. Best-effort — a failed cache bust or
    # revalidate must not roll back a published release.
    await cache.bust_feed(project.public_key)
    await _revalidate(project)

    if broadcast_id:
        # Hand off to the queue; the email consumer expands subscribers into
        # batches of ~50 and records per-recipient audit rows.
        enqueue(Queue.EMAIL, {"broadcast_id": broadcast_id})


async def _revalidate(project: Project) -> None:
    """Call the Next.js on-demand revalidation webhook for this tenant."""
    hook = getattr(settings, "revalidate_url", None)
    if not hook:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            await http.post(hook, json={"slug": project.slug})
    except Exception:
        log.warning("revalidate webhook failed for %s", project.slug)
