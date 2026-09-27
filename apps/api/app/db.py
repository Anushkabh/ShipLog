"""Async SQLAlchemy engine + session dependency.

The serverless connection trap (ARCHITECTURE §4): every warm Lambda container
handles one request at a time, so we keep SQLAlchemy's own pool tiny and let
Neon's PgBouncer endpoint do the real multiplexing.

Two hybrid-deployment concerns are handled here:

1. **PgBouncer + asyncpg prepared statements.** Neon's pooled endpoint runs
   PgBouncer in transaction mode, where asyncpg's cached prepared statements
   break ("prepared statement _pgN does not exist"). `statement_cache_size=0`
   disables that cache — required for the pooled endpoint, harmless direct.

2. **Lambda event loops.** The async consumers run one `asyncio.run()` per
   invocation, so a *retained* pooled connection would get reused across event
   loops and blow up ("attached to a different loop"). Inside Lambda we use
   `NullPool` (open/close per session); the long-lived container keeps a small
   pool and reuses its connection across back-to-back requests.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

_IN_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

_engine_kwargs: dict = {
    "echo": settings.debug and settings.env == "local",
    "pool_pre_ping": True,  # cheap liveness check; pooler may have dropped us
    # asyncpg must not reuse named prepared statements behind PgBouncer.
    "connect_args": {"statement_cache_size": 0},
}
if _IN_LAMBDA:
    _engine_kwargs["poolclass"] = NullPool  # no cross-invocation connection reuse
else:
    _engine_kwargs.update(pool_size=1, max_overflow=2, pool_recycle=300)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, always closed."""
    async with SessionLocal() as session:
        yield session
