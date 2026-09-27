# Setup Guide

Everything runs locally with zero cloud accounts (Phase 0). The optional sections below
each unlock one integration and can be done independently, in any order.

## Prerequisites

- Docker Desktop (for Postgres + Redis)
- Python 3.12 + [`uv`](https://docs.astral.sh/uv/) (`brew install uv`)
- Node.js 20+ (for the Next.js dashboard)

## 1. Core local stack (required)

```bash
# From repo root
docker compose up -d db redis            # Postgres :5432, Redis :6379

cd apps/api
uv sync                                  # install Python deps into .venv
cp .env.example .env                     # defaults work as-is for local
.venv/bin/alembic upgrade head           # create the schema
make run                                 # API on http://localhost:8000 (docs at /docs)
```

Verify the whole product loop end-to-end:

```bash
make smoke          # dev-login → project → release → publish → email fan-out → widget feed
```

## 2. Dashboard (required for the UI)

```bash
cd apps/web
npm install
npm run dev         # http://localhost:3000
```

Log in with **"Continue as Dev User"** on `/login` — no GitHub setup needed locally
(the dev-login endpoint only exists when `ENV=local`).

The frontend talks to the API at `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`), so no web-side env file is needed locally.

## 3. Optional: GitHub OAuth login

Only needed if you want real GitHub sign-in instead of dev-login.

1. GitHub → Settings → Developer settings → **OAuth Apps** → New OAuth App
   - Homepage URL: `http://localhost:3000`
   - Callback URL: `http://localhost:8000/auth/github/callback`
2. Put the credentials in `apps/api/.env`:
   ```
   GITHUB_CLIENT_ID=...
   GITHUB_CLIENT_SECRET=...
   ```

## 4. Optional: GitHub App (PR ingestion)

Powers the "connect a repo → merged PRs flow in" pipeline.

1. GitHub → Settings → Developer settings → **GitHub Apps** → New GitHub App
   - **Setup URL**: `http://localhost:8000/integrations/github/setup` — this is
     what makes one-click connect work; GitHub redirects the user's browser here
     after they install, so no tunnel is needed for it (only webhooks need one).
     Tick **"Redirect on update"** too, so adding/removing repos re-syncs.
   - Webhook URL: your API's `/webhooks/github` (use a tunnel like `ngrok http 8000`
     or `cloudflared` for local dev)
   - Webhook secret: any random string
   - Permissions: Pull requests (read), Contents (read), Metadata (read); subscribe
     to **Pull request** events
2. Generate a private key, then set in `apps/api/.env`:
   ```
   GITHUB_APP_ID=...
   GITHUB_APP_PRIVATE_KEY=...   # the PEM contents
   GITHUB_WEBHOOK_SECRET=...
   # GITHUB_APP_SLUG=...        # optional — auto-discovered from the API if blank
   ```
3. From the dashboard's **Integrations** page, click **Connect GitHub**. You'll be
   sent to GitHub to install the App and choose repos; on return, every repo you
   granted is connected automatically (no installation id to copy). Reconnecting or
   changing repos just re-syncs the list.

To test ingestion without any of this: `make` sure the API is running and run
`GITHUB_WEBHOOK_SECRET=test-webhook-secret .venv/bin/python scripts/smoke_ingest.py`
(set the same value in `.env` first).

## 5. Optional: AI drafting (BYOK)

No server-side key needed — each project brings its own. In the dashboard, open a
project → **AI** page → pick a provider and paste an API key (stored AES-256-GCM
encrypted). Supported: OpenAI, Anthropic, Gemini, Groq. Then use **"Draft with AI"**
in the release editor.

For any non-local environment, change `ENCRYPTION_KEY` (and `JWT_SECRET`) in `.env`
first — the dev defaults are intentionally insecure.

## 6. Optional: real email

Locally, `EMAIL_BACKEND=console` just logs emails to the API console — good enough to
see the fan-out work. For real delivery set either:

```
EMAIL_BACKEND=resend
RESEND_API_KEY=...
```

or `EMAIL_BACKEND=ses` with AWS credentials configured (boto3 default chain), plus a
verified `EMAIL_FROM` identity.

## 7. Not yet applicable (unbuilt)

- `QUEUE_BACKEND=sqs` + the `SQS_*_URL` vars — the code path exists, but there is no
  CDK infra yet to create the queues (`infra/` is empty).
- `packages/widget` — the embeddable widget.js is not written yet; the feed API it
  will consume already works.

## Day-to-day commands (apps/api/Makefile)

| Command | What it does |
|---|---|
| `make up` / `make down` | start/stop Postgres + Redis containers |
| `make run` | uvicorn with reload on :8000 |
| `make migrate` | `alembic upgrade head` |
| `make revision m="msg"` | autogenerate a migration |
| `make smoke` | end-to-end product-loop test |
| `make lint` | ruff |
