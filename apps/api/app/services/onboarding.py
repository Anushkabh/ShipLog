"""First-run setup: make a new project useful with as little typing as possible.

Two entry points:
  • load_sample_prs      — "Try with sample data": fills a project with realistic
                           merged PRs so the whole flow can be tried without a repo.
  • onboard_after_connect — runs in the background right after GitHub is
                           connected: pull recent PRs, import past releases, and
                           auto-fill the product context from the repo's docs.

Every step is best-effort and independent — one failing (e.g. a repo with no
docs, or AI not configured) must not stop the others.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import (
    IngestedItem,
    Integration,
    IntegrationProvider,
    Project,
    Release,
    ReleaseStatus,
    _id,
)
from app.services import ai, ai_access, backfill, github, importer
from app.services.sample_data import CASES, REPO

log = logging.getLogger("shiplog.onboarding")


async def load_sample_prs(db, project: Project) -> int:
    """Insert the sample PR set as merged "just now", so it all falls inside the
    next draft's window. One multi-row upsert (a single round trip); re-running
    just refreshes the same PR numbers."""
    now = datetime.now(UTC)
    rows = [
        {
            "id": _id(),
            "project_id": project.id,
            "provider": IntegrationProvider.GITHUB,
            "external_id": str(case.number),
            "title": case.title,
            "body": case.body,
            "labels": case.labels,
            "author": "sample-data",
            "url": f"https://github.com/{REPO}/pull/{case.number}",
            # Spread over the last few hours, newest last.
            "merged_at": now - timedelta(minutes=10 * (len(CASES) - i)),
        }
        for i, case in enumerate(CASES)
    ]
    stmt = pg_insert(IngestedItem).values(rows)
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_ingested_item",
            set_={
                "title": stmt.excluded.title,
                "body": stmt.excluded.body,
                "labels": stmt.excluded.labels,
                "merged_at": stmt.excluded.merged_at,
            },
        )
    )
    await db.commit()
    return len(rows)


async def _autofill_profile(db, project: Project, integrations: list[Integration]) -> bool:
    """Draft and SAVE the product context if the project has none yet."""
    if project.product_summary:
        return False
    for integ in integrations:
        docs = await github.gather_docs(integ.installation_id, integ.repo_full_name)
        if not docs:
            continue
        access = await ai_access.require(db, project)
        profile = await ai.infer_profile(
            access.provider, access.api_key, project.name, docs
        )
        project.product_summary = profile["product_summary"] or None
        project.audience = profile["audience"] or None
        project.tone = profile["tone"] or None
        await db.commit()
        return True
    return False


async def onboard_after_connect(project_id: str) -> None:
    """Background job fired by the GitHub connect callback."""
    async with SessionLocal() as db:
        project = await db.get(Project, project_id)
        if not project:
            return
        integrations = list(
            await db.scalars(
                select(Integration).where(Integration.project_id == project_id)
            )
        )

        for integ in integrations:
            try:
                await backfill.backfill_integration(db, integ)
            except Exception:
                log.exception("onboarding: backfill failed for %s", integ.repo_full_name)

        try:
            await importer.import_from_github_releases(db, project)
        except Exception:
            log.exception("onboarding: release import failed for %s", project_id)

        try:
            await _autofill_profile(db, project, integrations)
        except Exception:
            # Most commonly: no docs, or AI unavailable / over its daily limit.
            log.exception("onboarding: profile autofill skipped for %s", project_id)


async def setup_status(db, project: Project) -> dict:
    """Everything the Get started page needs, in ONE query (scalar subqueries),
    because the page polls it and each round trip counts."""
    pid = project.id
    last_published = (
        select(func.max(Release.published_at))
        .where(Release.project_id == pid, Release.status == ReleaseStatus.PUBLISHED)
        .scalar_subquery()
    )

    def count(model, *where):
        return select(func.count()).select_from(model).where(*where).scalar_subquery()

    row = (
        await db.execute(
            select(
                count(Integration, Integration.project_id == pid).label("repos"),
                count(
                    IngestedItem,
                    IngestedItem.project_id == pid,
                    or_(last_published.is_(None), IngestedItem.merged_at > last_published),
                ).label("pending"),
                count(Release, Release.project_id == pid).label("releases"),
                count(
                    Release, Release.project_id == pid,
                    Release.status == ReleaseStatus.PUBLISHED,
                ).label("published"),
                count(
                    Release, Release.project_id == pid,
                    Release.status.in_([ReleaseStatus.DRAFT, ReleaseStatus.SCHEDULED]),
                ).label("drafts"),
            )
        )
    ).one()
    return {
        "repos_connected": row.repos,
        "prs_pending": row.pending,
        "releases": row.releases,
        "published": row.published,
        "drafts": row.drafts,
        "profile_set": bool(project.product_summary),
        "ai_ready": (await ai_access.resolve(db, project)) is not None,
        "public_key": project.public_key,
    }
