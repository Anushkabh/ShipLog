# Shiplog — Project Overview

## What is this?

Shiplog is an **open-source, self-hostable release-notes & changelog platform** — an
alternative to paid SaaS tools like ReleaseNotes.io, Beamer, or LaunchNotes.

The product loop it implements:

1. **Connect a GitHub repo.** A GitHub App sends a webhook every time a PR is merged;
   Shiplog ingests those PRs as raw material for release notes.
2. **Draft with AI.** Bring your own LLM API key (OpenAI / Anthropic / Gemini / Groq).
   Shiplog turns the merged PRs plus your notes into a polished release-note draft,
   streamed live into a markdown editor.
3. **Edit & publish.** Markdown is sanitized to safe HTML at write time. Publishing is a
   single transaction that also busts caches and kicks off notifications.
4. **Distribute everywhere:**
   - A **hosted public changelog page** per project (`/c/<public-key>`), server-rendered
     by Next.js — shareable, SEO-friendly.
   - An **embeddable "What's new" widget** (`widget.js`) you drop into your own product,
     backed by a public Redis-cached feed API. *(feed API done; the JS widget itself is
     not yet written)*
   - **Email broadcasts** to double-opt-in subscribers, with HMAC-signed unsubscribe
     links, fanned out through a queue consumer.

## Who does it help?

- **Product / engineering teams** who ship regularly and want users to actually see
  what changed — without paying per-seat for a changelog SaaS or writing notes from
  scratch (the AI drafts from merged PRs).
- **Their end users**, who get a clean changelog page, an in-app "What's new" popover,
  and opt-in email updates.
- **You (the builder):** it's a realistic full-stack portfolio piece — multi-tenant auth,
  webhook ingestion with idempotency, queue abstraction, BYOK encryption, SSE streaming,
  SSR public pages — designed to run at **zero cost** on always-free tiers (Neon
  Postgres, Upstash Redis, AWS Lambda free tier) and to be self-hostable with one
  docker-compose file.

## The three-surfaces mental model

| Surface | Audience | Auth | Where |
|---|---|---|---|
| Dashboard | Your team | GitHub OAuth → JWT cookie | `apps/web` `(dashboard)` routes |
| Public changelog + widget feed | Your users | None (public key in URL) | `apps/web` `(public)` routes + `/api/v1/widget/*` |
| Machine surfaces | GitHub, email providers | HMAC signatures | `/webhooks/github`, email consumers |

## Key design decisions

- **Local-first, cloud-optional.** `QUEUE_BACKEND=local` runs consumers in-process with
  asyncio; flipping to `sqs` makes the exact same consumer code run as Lambda handlers.
  Same idea for email (`console` → `ses`/`resend`).
- **Sanitize at write time, not read time.** Markdown → HTML (markdown-it) → nh3
  allowlist happens once when a release is saved, so public endpoints serve
  pre-sanitized HTML.
- **Two idempotency layers for webhooks.** Unique `delivery_id` on `webhook_events`
  (dedup redeliveries) and a unique `(project_id, provider, external_id)` upsert on
  `ingested_items` (dedup reprocessing).
- **BYOK AI, encrypted at rest.** Per-project LLM keys stored AES-256-GCM encrypted;
  calls go through LiteLLM so one code path supports four providers.

## Where to go next

- [SETUP.md](SETUP.md) — get it running locally, and what to configure for each integration.
- [ARCHITECTURE.md](ARCHITECTURE.md) — the system as actually built (code map, data model, flows).
- [STATUS.md](STATUS.md) — what's done, what's missing, known issues.
