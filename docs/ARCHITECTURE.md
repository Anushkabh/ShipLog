# Architecture (as built)

This documents the system **as it exists in the code today**. (The README previously
linked an `ARCHITECTURE_v2.md` design doc that was never committed; this replaces it.)

## Monorepo layout

```
apps/api/          FastAPI backend — the whole product brain
  app/
    main.py        app factory; CORS; imports consumers so they self-register; Mangum handler for Lambda
    config.py      pydantic-settings; every var has a safe local default
    models.py      SQLAlchemy 2.0 async models (see data model below)
    security.py    JWT mint/verify, httpOnly cookie session
    deps.py        current_user, require_project(min_role) tenancy guard
    routers/       auth, projects, releases, subscribers, widget, webhooks, integrations, ai
    services/      render, crypto, cache, queue, email, github, ai, publish
    consumers/     webhook_proc, email_fanout (run in-process locally, as Lambdas in prod)
  alembic/         migrations (single initial schema)
  scripts/         smoke.py (product loop), smoke_ingest.py (webhook idempotency)
apps/web/          Next.js 15 App Router dashboard + public changelog
packages/widget/   (empty — planned embeddable widget.js)
infra/             (empty — planned AWS CDK: Lambda, SQS+DLQ, EventBridge)
```

## Backend

### Auth & tenancy

- **Login:** GitHub OAuth (`/auth/github/login` → callback, CSRF state cookie) or
  `/auth/dev-login` (404s unless `ENV=local`). First login auto-creates a personal
  Organization with an OWNER membership.
- **Session:** HS256 JWT in an httpOnly `SameSite=Lax` cookie ([security.py](../apps/api/app/security.py)).
- **Tenancy:** every project-scoped route goes through `require_project(min_role)`
  ([deps.py](../apps/api/app/deps.py)) with the role ladder viewer < editor < admin < owner.

### API surface

| Router | Prefix | Purpose |
|---|---|---|
| auth | `/auth` | OAuth, dev-login, logout, `me`, `me/orgs` |
| projects | `/api/projects` | list / create / get (no update/delete yet) |
| releases | `/api/projects/{pid}/releases` | CRUD + publish + private preview link |
| ai | `/api/projects/{pid}/ai` | BYOK credential PUT/GET + SSE `generate` |
| integrations | `/api/projects/{pid}/integrations` | connect / list / disconnect GitHub repos |
| widget | `/api/v1/widget` | **public** feed, release-by-slug, view counter (permissive CORS) |
| subscribers | `/api/v1/widget` | **public** subscribe, verify, unsubscribe |
| webhooks | `/webhooks` | GitHub App webhook receiver (HMAC-verified) |

### Services (the swappable seams)

Each service is env-switched so the same code runs locally and in the cloud:

- **queue.py** — `local`: fire-and-forget `asyncio.create_task` in-process;
  `sqs`: boto3 `send_message`. Consumers `register()` themselves at import.
- **email.py** — `console` (log only) | `ses` (boto3) | `resend` (HTTP). Always sets
  `List-Unsubscribe` headers.
- **cache.py** — `redis.asyncio`; feed cache + per-release view counters. Every
  operation is best-effort (exceptions swallowed) so Redis being down never 500s.
- **render.py** — markdown-it (commonmark, raw HTML off) → **nh3** allowlist sanitize.
  This is the XSS boundary; it runs at write time so reads serve pre-cleaned HTML.
- **crypto.py** — AES-256-GCM for stored AI keys (key derived from `ENCRYPTION_KEY`),
  HMAC signing for subscriber/unsubscribe tokens, SHA-256 for API-key hashes.
- **github.py** — webhook HMAC verify (constant-time), GitHub App RS256 JWT →
  installation token, `normalize_pr` (merged PRs only).
- **ai.py** — LiteLLM `acompletion(stream=True)`; per-provider default models
  (gpt-4o-mini / claude-3-5-haiku / gemini-1.5-flash / llama-3.3-70b). Lazy import.
- **publish.py** — the publish transaction: status flip, `published_at`, cache bust,
  (intended) Next.js revalidate ping, enqueue email broadcast.

### Event flows

**PR ingestion** (idempotent at two layers):

```
GitHub App webhook → POST /webhooks/github
  → HMAC verify
  → INSERT webhook_events ON CONFLICT (delivery_id) DO NOTHING   [layer 1: dedup redelivery]
  → enqueue → webhook_proc consumer
      → normalize_pr (merged only) → match repo to Integration
      → UPSERT ingested_items (project_id, provider, external_id) [layer 2: dedup reprocess]
```

**Publish → email:**

```
POST /releases/{id}/publish
  → publish.py: status=published, bust widget-feed cache
  → enqueue → email_fanout consumer
      → verified subscribers → per-recipient claim (ON CONFLICT DO NOTHING)
      → send via email backend with HMAC unsubscribe link
      → mark sent/failed on email_recipients, roll up counts on email_broadcasts
```

**AI drafting:** editor → `POST .../ai/generate` → decrypt project's key → LiteLLM
stream → SSE chunks straight into the editor textarea.

## Data model (18 tables)

```
users ─< organization_members >─ organizations ─< projects
projects ─< releases ─< release_tags >─ tags
         ─< integrations            (GitHub repo ↔ project)
         ─< ingested_items          (normalized merged PRs)
         ─< subscribers             (double opt-in)
         ─── ai_credentials         (1:1, encrypted BYOK key)
releases ─< reactions               (anon emoji — no API yet)
         ─< release_views_daily     (analytics rollup — no writer yet)
         ─< email_broadcasts ─< email_recipients >─ subscribers
webhook_events                      (idempotency layer 1)
api_keys                            (hashed — no API yet)
```

Releases carry `status` (draft/scheduled/published/archived), pre-rendered
`body_html`, optional `is_private` + `access_token` for preview links, and
`scheduled_at` (a scheduler to auto-publish these is not built yet).

## Frontend (apps/web)

Next.js 15 App Router, SWR for data fetching, Tailwind + a small custom UI kit.

- `/` — static marketing landing page.
- `/login` — GitHub OAuth button + dev-login (local only).
- `(dashboard)` — session-gated: projects list, releases table, markdown editor with
  live preview + streaming AI draft, AI credential page, integrations page.
- `(public)/c/[publicKey]` — SSR public changelog (index + per-release permalink),
  subscribe form. Fetches server-side via `lib/feed.ts` (`API_INTERNAL_URL`).

API base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Deployment model (planned, not yet built)

The code is already shaped for it: `main.py` exposes a **Mangum** handler (FastAPI on
Lambda), consumers are written as SQS handlers, and everything cloud-specific sits
behind an env var. The missing piece is the CDK app in `infra/` (Lambda + SQS + DLQ +
EventBridge scheduler) and the widget bundle in `packages/widget/`. Target free tiers:
Neon (Postgres), Upstash (Redis), AWS Lambda/SQS, SES/Resend, Vercel (web).
