"""FastAPI app + Mangum handler — the single mono-Lambda (ARCHITECTURE §4).

`uvicorn app.main:app` locally; `handler` is the Lambda entrypoint in prod.
Importing app.consumers.* registers the local queue handlers at startup so the
in-process worker path works with zero AWS.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings


def _find_widget_js() -> Path | None:
    """Locate packages/widget/widget.js by walking up from this file.

    Present in a repo checkout (local dev); absent in the API container, whose
    build context is apps/api only — there the web app serves /widget.js as a
    static file instead. Never raises: a missing file just means a 404 route.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packages" / "widget" / "widget.js"
        if candidate.is_file():
            return candidate
    return None


_WIDGET_JS = _find_widget_js()

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On a long-lived server (QUEUE_BACKEND=local) the scheduled-release
    # publisher runs in-process; on Lambda (lifespan="off") EventBridge calls
    # scheduler.publish_due_releases() instead.
    stop = asyncio.Event()
    task: asyncio.Task | None = None
    if settings.queue_backend == "local":
        from app.services.scheduler import run_scheduler

        task = asyncio.create_task(run_scheduler(stop))
    yield
    if task:
        stop.set()
        await task


app = FastAPI(
    title="Shiplog API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_prod else None,  # hide schema in prod
    lifespan=lifespan,
)

# Dashboard is same-origin via Next.js /api rewrite in prod, but during local
# dev the SPA is on :3000 and the API on :8000 → allow it with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "env": settings.env}


@app.get("/health/deep", tags=["meta"])
async def health_deep() -> dict:
    """Round-trip latency to the database and Redis, measured from the API's own
    host — the numbers that decide how fast every page feels."""
    import time

    from sqlalchemy import text

    from app.db import engine
    from app.services import cache

    def ms(t0: float) -> float:
        return round((time.perf_counter() - t0) * 1000, 1)

    db_ms: list[float] = []
    async with engine.connect() as conn:
        for _ in range(3):
            t0 = time.perf_counter()
            await conn.execute(text("select 1"))
            db_ms.append(ms(t0))
    redis_ms: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            await cache.client().ping()
            redis_ms.append(ms(t0))
        except Exception:
            redis_ms.append(-1)
    return {"db_round_trip_ms": db_ms, "redis_round_trip_ms": redis_ms}


@app.get("/widget.js", include_in_schema=False)
async def widget_js() -> FileResponse:
    if _WIDGET_JS is None:
        raise HTTPException(404, "widget.js is served by the web app in this deployment")
    return FileResponse(
        _WIDGET_JS,
        media_type="application/javascript",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300",
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────
from app.routers import (  # noqa: E402
    ai,
    auth,
    integrations,
    projects,
    releases,
    subscribers,
    webhooks,
    widget,
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(releases.router)
app.include_router(widget.router)
app.include_router(subscribers.router)
app.include_router(webhooks.router)
app.include_router(integrations.router)
app.include_router(integrations.setup_router)
app.include_router(ai.router)

# ── Register local queue consumers (self-register on import) ──────────────
from app.consumers import email_fanout, webhook_proc  # noqa: E402,F401

# ── Lambda entrypoint ─────────────────────────────────────────────────────
try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="off")
except ImportError:  # mangum optional for pure-local runs
    handler = None
