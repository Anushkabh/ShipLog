# Project Status

_Last reviewed: 2026-07-12 (full codebase audit)._

## ✅ Done and working

**Backend** — substantially complete:
- GitHub OAuth + dev-login, JWT cookie sessions, org/project multi-tenancy with roles
- Release CRUD, write-time markdown → sanitized HTML, publish transaction, private
  preview links
- Public widget feed + release-by-slug + view counter (Redis-cached, CORS-open)
- Subscribers: double opt-in, HMAC unsubscribe, email fan-out consumer with
  per-recipient audit trail
- GitHub App webhook ingestion with two idempotency layers → `ingested_items`
- AI drafting: BYOK (AES-256-GCM at rest), LiteLLM (OpenAI/Anthropic/Gemini/Groq),
  SSE streaming
- Queue + email + cache abstractions, env-switched local ↔ cloud
- Smoke scripts for the product loop and ingestion path

**Frontend** — further along than the README's 🚧 suggests:
- Landing page, login, dashboard shell (sidebar, org switcher, session gate)
- Projects list/create, releases table, full editor with live preview + AI streaming
- AI credential page, integrations page
- SSR public changelog (`/c/[publicKey]`) with subscribe form and permalinks

**Local dev experience** — docker-compose (Postgres+Redis), Makefile, `.env.example`
with working defaults, alembic migration.

## 🚧 Not built yet

| Gap | Notes |
|---|---|
| `packages/widget` (**empty**) | The embeddable widget.js is the core advertised feature; its feed API contract is done and tested by `smoke.py`. |
| `infra/` CDK (**empty**) | No deployment story yet. Code is Lambda-ready (Mangum, SQS handlers). |
| EventBridge cron for Path B | Scheduled publishing works in-process on long-lived servers (`services/scheduler.py`); a Lambda deployment still needs an EventBridge rule calling `publish_due_releases()`. |
| Analytics rollup + read API | Views accumulate in Redis but nothing flushes to `release_views_daily`, and no endpoint reads it. |
| Reactions API | `reactions` table exists, no endpoints. |
| API keys | `api_keys` table + hashing exist, no management endpoints. (Public subscribe endpoint now has per-IP rate limiting; broader API rate limiting still open.) |
| Subscribers & Settings dashboard pages | Sidebar shows them as `soon` (inert). |
| Project update/delete endpoints | Only list/create/get exist. |
| Unit tests | `make test` collects nothing; only the two live-stack smoke scripts exist. |

## 🐛 Known issues

1. **Dead revalidate path.** `services/publish.py` reads
   `getattr(settings, "revalidate_url", None)` but `Settings` has no such field, so the
   Next.js on-demand revalidation ping never fires. Public pages currently rely on
   time-based ISR instead. Fix: add the setting + a revalidate route in the web app,
   or delete the branch.
2. **README drift.** Lists the dashboard/public sites as 🚧 though they're built; the
   docker-compose comment mentions an `api` service that isn't defined.

### Fixed (2026-07-12)

- ~~AI provider enum mismatch~~ — frontend now sends `gemini` matching the backend enum.
- ~~Scheduled releases never publish~~ — `services/scheduler.py` polls every 60s
  (FOR UPDATE SKIP LOCKED, per-release transactions) via app lifespan when
  `QUEUE_BACKEND=local`; `publish_due_releases()` is reusable by the future
  EventBridge Lambda.
- ~~Unthrottled public subscribe~~ — per-IP fixed-window rate limit
  (10/hour, Redis INCR+EXPIRE, fail-open) on `POST /subscribe`.
- ~~Broken `ARCHITECTURE_v2.md` link~~ — README now points at [docs/](.).

## Suggested next steps (in rough priority order)

1. Build `packages/widget/widget.js` — the feed contract is stable and smoke-tested;
   this closes the biggest gap between the pitch and the product.
2. Subscribers dashboard page (table + counts — the data model is all there).
3. Unit tests around the security seams (render/sanitize, HMAC verify, crypto, tenancy).
4. Deploy via [DEPLOYMENT.md](DEPLOYMENT.md) Path A; CDK infra later if/when you want
   the serverless architecture.
