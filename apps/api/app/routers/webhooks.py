"""GitHub webhook receiver (ARCHITECTURE §6).

POST /webhooks/github does the minimum fast, transactional work and returns 200
in well under a second:
  1. Verify X-Hub-Signature-256 (constant-time HMAC) — reject forgeries.
  2. Insert a webhook_events row keyed by X-GitHub-Delivery (UNIQUE) —
     IDEMPOTENCY LAYER 1: GitHub redelivers on timeout, the unique constraint
     makes a retry a no-op instead of a duplicate storm.
  3. Enqueue the event id for async processing; the heavy lifting (normalize +
     upsert into ingested_items) happens in the consumer.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.deps import DbDep
from app.models import WebhookEvent
from app.services.github import verify_signature
from app.services.queue import Queue, enqueue

log = logging.getLogger("shiplog.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(request: Request, db: DbDep) -> Response:
    body = await request.body()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature")

    delivery_id = request.headers.get("X-GitHub-Delivery")
    event = request.headers.get("X-GitHub-Event", "unknown")
    if not delivery_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing delivery id")

    payload = await request.json()

    # We only care about pull_request events for the changelog pipeline; ack
    # everything else fast so GitHub stops retrying but we do no work.
    if event != "pull_request":
        return Response(status_code=202)

    # Idempotency layer 1: ON CONFLICT DO NOTHING on the unique delivery_id.
    result = await db.execute(
        pg_insert(WebhookEvent)
        .values(
            delivery_id=delivery_id,
            event=event,
            action=payload.get("action"),
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["delivery_id"])
        .returning(WebhookEvent.id)
    )
    row_id = result.scalar_one_or_none()
    await db.commit()

    if row_id is None:
        # Duplicate delivery — already have it. Ack without re-enqueueing.
        log.info("duplicate delivery %s ignored", delivery_id)
        return Response(status_code=200)

    enqueue(Queue.WEBHOOK, {"webhook_event_id": row_id})
    return Response(status_code=200)
