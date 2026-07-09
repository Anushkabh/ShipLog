"""Email fan-out consumer (ARCHITECTURE §8).

Body: {"broadcast_id": "..."}  (or {"broadcast_id", "subscriber_ids": [...]}
for a single re-tryable batch — prod SQS path splits into ~50s upstream).

Idempotency: EmailRecipient has UNIQUE(broadcast_id, subscriber_id). We
insert-or-skip per recipient, so an at-least-once redelivery can never email the
same person twice. Each row records queued/sent/failed for an auditable log.

Runs identically as a local asyncio task now and a Lambda SQS handler later.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import (
    BroadcastStatus,
    EmailBroadcast,
    EmailRecipient,
    Project,
    RecipientStatus,
    Release,
    Subscriber,
)
from app.services import crypto
from app.services.email import send_email
from app.services.queue import Queue, register

log = logging.getLogger("shiplog.email_fanout")

_BATCH = 50


async def handle(body: dict) -> None:
    broadcast_id = body["broadcast_id"]
    async with SessionLocal() as db:
        broadcast = await db.get(EmailBroadcast, broadcast_id)
        if not broadcast:
            return
        release = await db.get(Release, broadcast.release_id)
        project = await db.get(Project, release.project_id) if release else None
        if not release or not project:
            return

        subs = list(
            await db.scalars(
                select(Subscriber).where(
                    Subscriber.project_id == project.id,
                    Subscriber.verified.is_(True),
                )
            )
        )
        broadcast.status = BroadcastStatus.SENDING
        broadcast.total_count = len(subs)
        await db.commit()

        sent = 0
        for sub in subs:
            # Idempotency: claim this recipient. ON CONFLICT DO NOTHING means a
            # redelivery that already sent to this person is a no-op.
            res = await db.execute(
                pg_insert(EmailRecipient)
                .values(
                    broadcast_id=broadcast_id,
                    subscriber_id=sub.id,
                    status=RecipientStatus.QUEUED,
                )
                .on_conflict_do_nothing(index_elements=["broadcast_id", "subscriber_id"])
                .returning(EmailRecipient.id)
            )
            recipient_id = res.scalar_one_or_none()
            if recipient_id is None:
                continue  # already handled in a prior delivery
            await db.commit()

            unsub = crypto.sign(sub.unsub_token)
            from app.config import settings

            unsub_url = f"{settings.api_url}/api/v1/widget/unsubscribe/{unsub}"
            try:
                await send_email(
                    to=sub.email,
                    subject=f"{project.name}: {release.title}",
                    html=release.body_html
                    + f'<hr><p style="font-size:12px"><a href="{unsub_url}">Unsubscribe</a></p>',
                    list_unsubscribe=unsub_url,
                )
                await _mark(db, recipient_id, RecipientStatus.SENT)
                sent += 1
            except Exception as e:  # noqa: BLE001 — record and continue
                await _mark(db, recipient_id, RecipientStatus.FAILED, str(e))
                log.warning("send to %s failed: %s", sub.email, e)

        broadcast.sent_count = sent
        broadcast.status = BroadcastStatus.SENT
        await db.commit()


async def _mark(db, recipient_id, status, error=None) -> None:
    row = await db.get(EmailRecipient, recipient_id)
    row.status = status
    row.error = error
    if status == RecipientStatus.SENT:
        row.sent_at = datetime.now(UTC)
    await db.commit()


register(Queue.EMAIL, handle)
