"""Backfill merged PRs for a connected repo (ARCHITECTURE §6).

Webhooks only deliver PRs merged *after* a repo is connected, so a freshly
onboarded project would have nothing to draft from. This pulls recent history
via the GitHub API and upserts it through the SAME idempotency key the webhook
consumer uses — running backfill and then receiving a webhook for the same PR is
harmless.

`run_for_integration` opens its own session so it can run detached from the
request that triggered it (connect-time fire-and-forget) as well as inline from
the manual "Sync" endpoint.
"""

from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import IngestedItem, Integration, IntegrationProvider
from app.services import github

log = logging.getLogger("shiplog.backfill")


async def upsert_item(db, project_id: str, item: dict) -> None:
    """Idempotent insert on (project_id, provider, external_id).

    Shared by the webhook consumer and backfill so both paths dedup identically.
    Never overwrites `release_id` — a re-sync must not detach a PR already used
    in a release.
    """
    await db.execute(
        pg_insert(IngestedItem)
        .values(
            project_id=project_id,
            provider=IntegrationProvider.GITHUB,
            external_id=item["external_id"],
            title=item["title"],
            body=item["body"],
            labels=item["labels"],
            author=item["author"],
            url=item["url"],
            merged_at=item["merged_at"],
        )
        .on_conflict_do_update(
            constraint="uq_ingested_item",
            set_={
                "title": item["title"],
                "body": item["body"],
                "labels": item["labels"],
                "author": item["author"],
                "merged_at": item["merged_at"],
            },
        )
    )


async def backfill_integration(db, integration: Integration, limit: int = 50) -> int:
    """Pull recent merged PRs for one integration and upsert them. Returns count."""
    prs = await github.list_merged_prs(
        integration.installation_id, integration.repo_full_name, limit=limit
    )
    for pr in prs:
        await upsert_item(db, integration.project_id, pr)
    await db.commit()
    log.info(
        "backfilled %d PRs for %s (project %s)",
        len(prs), integration.repo_full_name, integration.project_id,
    )
    return len(prs)


async def run_for_integration(integration_id: str, limit: int = 50) -> int:
    """Detached entrypoint: load the integration in a fresh session and backfill.

    Best-effort — a GitHub hiccup here must never surface as a failed connect.
    """
    try:
        async with SessionLocal() as db:
            integration = await db.get(Integration, integration_id)
            if not integration:
                return 0
            return await backfill_integration(db, integration, limit=limit)
    except Exception:
        log.exception("backfill failed for integration %s", integration_id)
        return 0
