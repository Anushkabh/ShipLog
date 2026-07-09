"""Redis: widget-feed cache + view counters (ARCHITECTURE §3, §10).

The widget feed is the hot read path — it must never touch Postgres on a cache
hit. We cache the JSON blob per project_public_key and bust it on publish. View
counts are Redis INCRs flushed to Postgres by the cron, so the hot path does no
DB write.

Uses redis.asyncio; works against local redis and Upstash (redis:// over TLS).
"""

from __future__ import annotations

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def feed_key(public_key: str) -> str:
    return f"feed:{public_key}"


async def get_feed(public_key: str) -> str | None:
    try:
        return await client().get(feed_key(public_key))
    except Exception:
        return None  # cache is best-effort; fall through to DB


async def set_feed(public_key: str, payload: str, ttl: int = 300) -> None:
    try:
        await client().set(feed_key(public_key), payload, ex=ttl)
    except Exception:
        pass


async def bust_feed(public_key: str) -> None:
    try:
        await client().delete(feed_key(public_key))
    except Exception:
        pass


# ── View counters (§10): INCR view:{release_id}:{yyyy-mm-dd} ──────────────
async def incr_view(release_id: str, day: str) -> None:
    try:
        await client().incr(f"view:{release_id}:{day}")
    except Exception:
        pass
