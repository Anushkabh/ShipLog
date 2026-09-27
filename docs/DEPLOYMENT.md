# Production Deployment Guide

How to move Shiplog from local dev to a real, publicly reachable deployment.

There are two viable paths. **Start with Path A** — it needs zero new code and gets you
live in an afternoon. Path B is the architecture the code was designed for (Lambda +
SQS via CDK) but requires writing all of `infra/` first.

| | Path A — long-lived server | Path B — AWS serverless |
|---|---|---|
| API host | Fly.io / Railway / Render (Docker) | Lambda (Mangum) + API Gateway |
| Queue | `QUEUE_BACKEND=local` (in-process, fine on a long-lived server) | `QUEUE_BACKEND=sqs` + consumer Lambdas |
| New code needed | none | entire CDK app in `infra/` |
| Cost | ~$0–5/mo | ~$0 (free tier) but more setup |

Both paths share everything below except step 7.

---

## 0. Code fixes to make first (blockers)

All three done 2026-07-12:

1. ~~`google` vs `gemini` provider mismatch~~ — frontend now sends `gemini`.
2. ~~Scheduled releases~~ — `app/services/scheduler.py` publishes due releases every
   60s in-process (started via app lifespan when `QUEUE_BACKEND=local`, i.e. Path A
   and local dev). Path B still needs an EventBridge cron Lambda calling
   `scheduler.publish_due_releases()`.
3. ~~Subscribe rate limiting~~ — `POST /api/v1/widget/{key}/subscribe` is limited to
   10/hour per client IP (Redis fixed window, fail-open if Redis is down).

Non-blocking but worth doing: delete or wire the dead `revalidate_url` branch in
`services/publish.py` (public pages currently rely on time-based ISR, which is fine).

## 1. Domain

Buy a domain (the code's default `shiplog.app` is a placeholder — set yours via
`ROOT_DOMAIN`). Plan the subdomains; the session cookie is scoped to
`.{ROOT_DOMAIN}`, so **dashboard and API must live under the same root domain**:

```
app.yourdomain.com   → Next.js (Vercel)
api.yourdomain.com   → FastAPI
```

DNS: two CNAME records, created in steps 6–7.

## 2. Managed Postgres — Neon (free tier)

1. Create a project at neon.tech (pick a region near your API host).
2. Copy the **pooled** connection string (PgBouncer endpoint) and convert the scheme
   for asyncpg: `postgresql+asyncpg://user:pass@...-pooler.../dbname?ssl=require`.
3. Run migrations against it once, from your machine:
   ```bash
   cd apps/api
   DATABASE_URL="postgresql+asyncpg://..." .venv/bin/alembic upgrade head
   ```

## 3. Managed Redis — Upstash (free tier)

Create a database at upstash.com, copy the TLS URL (`rediss://...`) → `REDIS_URL`.
Cache code is best-effort, so Redis problems degrade to slower responses, never errors.

## 4. Secrets

Generate real values (the dev defaults are intentionally insecure):

```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_hex(32))"
```

⚠️ `ENCRYPTION_KEY` encrypts customers' BYOK AI keys at rest. Once set in prod,
**never rotate it casually** — existing stored keys become undecryptable. Store both
secrets only in the host's env config, never in git.

## 5. GitHub apps (production copies)

Keep your local OAuth/GitHub Apps for dev; create separate prod ones.

**OAuth App** (login): callback `https://api.yourdomain.com/auth/github/callback`
→ `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`.

**GitHub App** (PR ingestion): webhook URL `https://api.yourdomain.com/webhooks/github`,
a strong random webhook secret, Pull requests (read) permission, Pull request events
→ `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` (PEM contents) / `GITHUB_WEBHOOK_SECRET`.
No tunnel needed anymore — the API is publicly reachable.

## 6. Email — Resend (simplest) or SES

**Resend:** add your domain, create the DNS records it gives you (SPF, DKIM), get an
API key. Set:

```
EMAIL_BACKEND=resend
RESEND_API_KEY=re_...
EMAIL_FROM=YourProduct <updates@yourdomain.com>
```

**SES alternative:** verify the domain, request production access (out of sandbox),
give the API host AWS credentials, set `EMAIL_BACKEND=ses`.

Free tiers: Resend 3k emails/mo; SES 62k/mo from EC2/Lambda. Start with Resend.

## 7A. Path A — API on a long-lived server (recommended first)

Add a Dockerfile at `apps/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Deploy to Fly.io / Railway / Render with this environment:

```
ENV=prod                    # enables Secure cookies, hides /docs, disables dev-login
DEBUG=false
APP_URL=https://app.yourdomain.com
API_URL=https://api.yourdomain.com
ROOT_DOMAIN=yourdomain.com
DATABASE_URL=postgresql+asyncpg://...neon pooled...
REDIS_URL=rediss://...upstash...
JWT_SECRET=...            ENCRYPTION_KEY=...
GITHUB_CLIENT_ID=...      GITHUB_CLIENT_SECRET=...
GITHUB_APP_ID=...         GITHUB_APP_PRIVATE_KEY=...   GITHUB_WEBHOOK_SECRET=...
EMAIL_BACKEND=resend      RESEND_API_KEY=...           EMAIL_FROM=...
QUEUE_BACKEND=local       # in-process asyncio — correct for a long-lived server
```

Point `api.yourdomain.com` (CNAME) at the service; the platform provisions TLS.

Notes:
- `QUEUE_BACKEND=local` is production-correct here: the process is long-lived, so
  email fan-out and webhook processing run as background asyncio tasks. The tradeoff
  vs SQS is no retry/DLQ if the process dies mid-job.
- Avoid platforms/plans that **sleep** the instance if you rely on scheduled publishing
  or want webhook processing to be instant; Fly/Railway always-on tiers are ~$2–5/mo.

## 7B. Path B — AWS serverless (the designed target)

What has to be built in `infra/` (Python CDK):

1. **Mono API Lambda** — package `apps/api` (Docker image or zip + layer), handler
   `app.main.handler` (Mangum, already written), behind an HTTP API Gateway with a
   custom domain (`api.yourdomain.com`, ACM cert).
2. **Three SQS queues + DLQs** — webhook, email, ai → env vars `SQS_WEBHOOK_URL`,
   `SQS_EMAIL_URL`, `SQS_AI_URL`; set `QUEUE_BACKEND=sqs`.
3. **Consumer Lambdas** — same codebase, entry points wrapping
   `app/consumers/webhook_proc.py` and `email_fanout.py` with SQS event sources
   (small Lambda-handler shims still need writing).
4. **EventBridge cron** (every minute) → a Lambda that publishes due scheduled
   releases (`SELECT ... FOR UPDATE SKIP LOCKED` — the query/handler needs writing).
5. **IAM**: API Lambda gets `sqs:SendMessage`; consumers get receive/delete; SES send
   if using SES.

Same env vars as Path A otherwise. Do this later — nothing about Path A locks you out
of it, since every seam is already env-switched.

## 8. Frontend on Vercel

1. Import the repo in Vercel, set **Root Directory = `apps/web`** (Next.js preset).
2. Env vars:
   ```
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   API_INTERNAL_URL=https://api.yourdomain.com
   ```
3. Add the custom domain `app.yourdomain.com`.

CORS already handles this: the API allows `APP_URL` with credentials, and the session
cookie is set on `.yourdomain.com`, so `app.` ↔ `api.` requests carry it.

## 9. Post-deploy verification

1. `https://api.yourdomain.com/health` → `{"status":"ok","env":"prod"}`
2. `/docs` returns 404 (hidden in prod) and `/auth/dev-login` returns 404 (local-only).
3. Log in with GitHub at `app.yourdomain.com` → cookie set → dashboard loads.
4. Create a project → release → publish. Check the public page
   `app.yourdomain.com/c/<publicKey>` and the feed
   `api.yourdomain.com/api/v1/widget/<publicKey>/feed`.
5. Subscribe with a real email → verify link arrives → publish again → broadcast
   arrives with a working unsubscribe link.
6. Connect a real repo via the GitHub App, merge a test PR, confirm a row lands in
   `ingested_items` (webhook → queue → consumer, end to end).
7. Save an AI key on the AI page and stream a draft in the editor.

## 10. Ongoing / hardening

- **Backups:** Neon free tier keeps limited history — enable/verify point-in-time
  restore; export dumps periodically for safety.
- **Monitoring:** platform logs + an uptime ping on `/health` (UptimeRobot free).
  Sentry's free tier works with FastAPI and Next.js if you want error tracking.
- **Deploy pipeline:** GitHub Actions — run `alembic upgrade head` against Neon, then
  deploy API and web. Vercel auto-deploys the web app on push either way.
- Still open from [STATUS.md](STATUS.md): the embeddable widget.js, analytics rollup,
  API keys + rate limiting, subscribers dashboard page, unit tests.
