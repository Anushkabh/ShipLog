# Shiplog

Open-source, self-hostable release-notes & changelog platform — an alternative
to ReleaseNotes.io. Connect a GitHub repo, let AI draft release notes from
merged PRs, publish to a hosted changelog, push updates into your own product
via an embeddable widget, and broadcast to email subscribers.

**Stack:** FastAPI (Python 3.12, async) · SQLAlchemy 2.0 + Postgres (Neon) ·
Next.js 15 · AWS Lambda/SQS/EventBridge (CDK) · Upstash Redis · SES. Designed to
run at effectively **zero cost** on always-free tiers. See
[`ARCHITECTURE_v2.md`](ARCHITECTURE_v2.md) for the full design and rationale.

## Monorepo layout

```
apps/api/          FastAPI backend (app/, alembic/, scripts/)
apps/web/          Next.js dashboard + public changelog sites (TBD)
packages/widget/   widget.js — the embeddable "What's new" widget
infra/             AWS CDK (Python) — Lambda, SQS+DLQ, EventBridge (TBD)
docker-compose.yml Local self-host: Postgres + Redis
```

## Local dev (Phase 0 — zero AWS)

Everything runs locally with an in-process queue worker; no cloud needed.

```bash
# 1. Toolchain
brew install uv
cd apps/api && uv sync

# 2. Infra
docker compose up -d db redis        # from repo root
cp apps/api/.env.example apps/api/.env

# 3. Schema
cd apps/api && .venv/bin/alembic upgrade head

# 4. Run
make run                             # uvicorn on :8000, docs at /docs

# 5. Prove the whole product loop end-to-end
make smoke
```

`make smoke` performs: dev-login → create project → create release (markdown is
sanitized to HTML at write time) → publish (fires the local email fan-out
consumer) → fetch the widget feed and assert it matches the contract
`widget.js` consumes.

## What's built so far

- ✅ Async SQLAlchemy models + Neon-pooled engine
- ✅ GitHub OAuth login + JWT httpOnly session cookies + org/project tenancy
- ✅ Release CRUD, write-time markdown sanitize (`nh3`), publish transaction
- ✅ Widget feed endpoint (Redis-cached) — serves `widget.js`
- ✅ Subscribers (double opt-in) + HMAC unsubscribe + email fan-out consumer
- ✅ Queue abstraction (local in-process ↔ SQS) — flip one env var
- ✅ GitHub App ingestion: signed webhook (HMAC) + both idempotency layers → `ingested_items`
- ✅ AI drafting (LiteLLM BYOK, AES-256-GCM key at rest, SSE streaming endpoint)
- 🚧 EventBridge scheduler (SKIP LOCKED), API keys + rate limiting, analytics rollup
- 🚧 AWS CDK infra, Next.js dashboard + public sites

Smoke tests: `scripts/smoke.py` (product loop) and `scripts/smoke_ingest.py`
(ingestion + idempotency) — both verified passing.
```
