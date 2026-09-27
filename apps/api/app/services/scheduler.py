"""Publishes releases whose scheduled_at has arrived (ARCHITECTURE §8).

`publish_due_releases()` is the single unit of work, shared by two runners:
  - the in-process loop below (long-lived server / local dev), started from the
    app lifespan when QUEUE_BACKEND=local
  - the future EventBridge cron Lambda (Path B), which calls it once per tick

Each due release is claimed in its own transaction with FOR UPDATE SKIP LOCKED
and its status re-checked, so concurrent runners never double-publish (and
never double-enqueue the email broadcast).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Release, ReleaseStatus
from app.services.publish import publish_release

log = logging.getLogger("shiplog.scheduler")

TICK_SECONDS = 60
PURGE_EVERY_SECONDS = 3600  # expired demo workspaces are swept hourly


async def purge_demos() -> int:
    """Delete demo sandboxes past their TTL. Best-effort; never raises."""
    from app.services.demo import purge_expired_demos  # avoid import cycle

    try:
        async with SessionLocal() as db:
            return await purge_expired_demos(db)
    except Exception:
        log.exception("demo purge failed")
        return 0


async def publish_due_releases() -> int:
    """Publish every scheduled release that is due. Returns how many."""
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        due_ids = list(
            await db.scalars(
                select(Release.id).where(
                    Release.status == ReleaseStatus.SCHEDULED,
                    Release.scheduled_at <= now,
                )
            )
        )

    published = 0
    for release_id in due_ids:
        async with SessionLocal() as db:
            release = await db.scalar(
                select(Release)
                .where(
                    Release.id == release_id,
                    Release.status == ReleaseStatus.SCHEDULED,
                )
                .with_for_update(skip_locked=True)
            )
            if release is None:  # another runner claimed it
                continue
            project = await db.get(Project, release.project_id)
            await publish_release(db, project, release)
            published += 1
            log.info("published scheduled release %s", release_id)
    return published


async def run_scheduler(stop: asyncio.Event) -> None:
    """Tick every TICK_SECONDS until `stop` is set. Errors never kill the loop."""
    log.info("scheduler loop started (every %ss)", TICK_SECONDS)
    last_purge = 0.0
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        try:
            await publish_due_releases()
        except Exception:
            log.exception("scheduler tick failed")
        if loop.time() - last_purge >= PURGE_EVERY_SECONDS:
            await purge_demos()
            last_purge = loop.time()
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_SECONDS)
        except TimeoutError:
            pass
    log.info("scheduler loop stopped")
