"""Queue abstraction: one `enqueue()` API, two backends.

Local (Phase 0): run the consumer coroutine as a fire-and-forget asyncio task
in the same process — proves the event-driven product loop with zero cloud.
Prod: `send_message` to the matching SQS queue; a Lambda consumer picks it up.

The consumer code is identical either way (see app/consumers/*): it takes a
plain dict `body` and is idempotent, because SQS is at-least-once and the local
worker can also double-fire on retries. Flip QUEUE_BACKEND to switch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from enum import Enum

from app.config import settings

log = logging.getLogger("shiplog.queue")

Handler = Callable[[dict], Awaitable[None]]


class Queue(str, Enum):
    WEBHOOK = "webhook"
    EMAIL = "email"
    AI = "ai"


_URLS = {
    Queue.WEBHOOK: lambda: settings.sqs_webhook_url,
    Queue.EMAIL: lambda: settings.sqs_email_url,
    Queue.AI: lambda: settings.sqs_ai_url,
}

# Local backend: consumers self-register here at import time.
_handlers: dict[Queue, Handler] = {}
_background_tasks: set[asyncio.Task] = set()


def register(queue: Queue, handler: Handler) -> None:
    _handlers[queue] = handler


async def _run_local(queue: Queue, body: dict) -> None:
    handler = _handlers.get(queue)
    if handler is None:
        log.warning("no local handler registered for queue %s", queue.value)
        return
    try:
        await handler(body)
    except Exception:  # never let a background job crash the request path
        log.exception("local consumer for %s failed", queue.value)


def enqueue(queue: Queue, body: dict) -> None:
    """Hand work to a queue. Returns immediately; never blocks the request."""
    if settings.queue_backend == "sqs":
        import boto3  # lazy: keep cold start lean

        boto3.client("sqs").send_message(
            QueueUrl=_URLS[queue](), MessageBody=json.dumps(body)
        )
        return

    # Local: schedule the consumer without awaiting it. Keep a strong ref so the
    # task isn't garbage-collected mid-flight.
    task = asyncio.create_task(_run_local(queue, body))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
