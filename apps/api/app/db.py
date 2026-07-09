"""Async SQLAlchemy engine + session dependency.

The serverless connection trap (ARCHITECTURE §4): every warm Lambda container
handles one request at a time, so we keep SQLAlchemy's own pool tiny and let
Neon's PgBouncer endpoint do the real multiplexing. `pool_size=1` +
`max_overflow` small means a burst of 100 Lambdas opens ~100 *pooler* client
connections, which PgBouncer collapses onto a handful of real Postgres ones.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# NullPool is another valid choice on Lambda (open/close per invocation and rely
# entirely on the external pooler). We keep a size-1 pool so a warm container
# reuses its connection across back-to-back requests, which is the common case.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug and settings.env == "local",
    pool_size=1,
    max_overflow=2,
    pool_pre_ping=True,   # cheap liveness check; pooler may have dropped us
    pool_recycle=300,
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, always closed."""
    async with SessionLocal() as session:
        yield session
