"""FastAPI app + Mangum handler — the single mono-Lambda (ARCHITECTURE §4).

`uvicorn app.main:app` locally; `handler` is the Lambda entrypoint in prod.
Importing app.consumers.* registers the local queue handlers at startup so the
in-process worker path works with zero AWS.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Shiplog API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_prod else None,  # hide schema in prod
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
app.include_router(ai.router)

# ── Register local queue consumers (self-register on import) ──────────────
from app.consumers import email_fanout, webhook_proc  # noqa: E402,F401

# ── Lambda entrypoint ─────────────────────────────────────────────────────
try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="off")
except ImportError:  # mangum optional for pure-local runs
    handler = None
