"""AWS Lambda entrypoints for the async backbone (hybrid deployment).

The API runs on a long-lived container (streaming, no cold starts). The async
work runs here on Lambda, invoking the SAME consumer code:

  webhook_consumer  — SQS-triggered → app.consumers.webhook_proc.handle
  email_consumer    — SQS-triggered → app.consumers.email_fanout.handle
  scheduler_handler — EventBridge cron → services.scheduler.publish_due_releases

Each invocation runs its own event loop via asyncio.run(); db.py uses NullPool
in Lambda so DB connections never cross loops. The SQS handlers return
`batchItemFailures` (partial-batch responses) so only failed messages are
retried — enable "Report batch item failures" on the event source mapping.

Requires QUEUE_BACKEND=sqs in the Lambda env so any work these enqueue (the
scheduler enqueues email broadcasts) goes back to SQS, not an in-process task.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shiplog.lambda")


async def _process_batch(
    records: list[dict], handler: Callable[[dict], Awaitable[None]]
) -> list[dict]:
    """Run one async handler per SQS record; collect the ids that failed so SQS
    redrives only those (the rest are deleted)."""
    failures: list[dict] = []
    for rec in records:
        try:
            body = json.loads(rec["body"])
            await handler(body)
        except Exception:
            log.exception("record %s failed", rec.get("messageId"))
            failures.append({"itemIdentifier": rec["messageId"]})
    return failures


def webhook_consumer(event: dict, context: object) -> dict:
    from app.consumers.webhook_proc import handle

    failures = asyncio.run(_process_batch(event.get("Records", []), handle))
    return {"batchItemFailures": failures}


def email_consumer(event: dict, context: object) -> dict:
    from app.consumers.email_fanout import handle

    failures = asyncio.run(_process_batch(event.get("Records", []), handle))
    return {"batchItemFailures": failures}


def scheduler_handler(event: dict, context: object) -> dict:
    """EventBridge cron tick: publish any releases whose schedule has arrived."""
    from app.services.scheduler import publish_due_releases

    published = asyncio.run(publish_due_releases())
    return {"published": published}
