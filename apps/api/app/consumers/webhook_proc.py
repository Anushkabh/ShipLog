"""Webhook processing consumer (ARCHITECTURE §6) — IDEMPOTENCY LAYER 2.

Body: {"webhook_event_id": "..."}

Loads the raw WebhookEvent, normalizes the merged-PR payload, and UPSERTs an
IngestedItem on (project_id, provider, external_id). SQS is at-least-once, so
this must be idempotent — the ON CONFLICT DO UPDATE makes reprocessing harmless
(same PR just refreshes title/labels). Marks the WebhookEvent processed.

We resolve which project owns the event by matching the repo full name against
the Integration table (a repo can only be connected to one project).

Runs identically as a local asyncio task now and a Lambda SQS handler later.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import IngestedItem, Integration, IntegrationProvider, WebhookEvent
from app.services.github import normalize_pr
from app.services.queue import Queue, register

log = logging.getLogger("shiplog.webhook_proc")


async def handle(body: dict) -> None:
    event_id = body["webhook_event_id"]
    async with SessionLocal() as db:
        event = await db.get(WebhookEvent, event_id)
        if not event or event.processed:
            return  # gone or already done — idempotent no-op

        item = normalize_pr(event.payload)
        if item is None:
            # Not a merged PR (opened, closed-unmerged, etc.) — nothing to ingest.
            event.processed = True
            await db.commit()
            return

        repo = item.pop("repo_full_name", None)
        integration = await db.scalar(
            select(Integration).where(
                Integration.repo_full_name == repo,
                Integration.provider == IntegrationProvider.GITHUB,
            )
        )
        if not integration:
            log.warning("no integration for repo %s; dropping PR", repo)
            event.processed = True
            await db.commit()
            return

        # Idempotency layer 2: upsert on the natural key.
        await db.execute(
            pg_insert(IngestedItem)
            .values(
                project_id=integration.project_id,
                provider=IntegrationProvider.GITHUB,
                **item,
            )
            .on_conflict_do_update(
                index_elements=["project_id", "provider", "external_id"],
                set_={
                    "title": item["title"],
                    "body": item["body"],
                    "labels": item["labels"],
                    "author": item["author"],
                    "merged_at": item["merged_at"],
                },
            )
        )
        event.processed = True
        await db.commit()
        log.info("ingested PR %s for project %s", item["external_id"], integration.project_id)


register(Queue.WEBHOOK, handle)
