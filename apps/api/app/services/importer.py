"""Import a project's prior release notes from GitHub Releases.

Imported entries become real PUBLISHED Release rows, which does three useful
things at once:
  • the customer's changelog is pre-populated with their real history,
  • the public page and widget show it immediately,
  • the AI pipeline picks recent ones up as few-shot VOICE examples (it already
    pulls recent published releases), so a brand-new project's first AI draft
    already sounds like the team — killing the cold-start problem.

Idempotent: dedup is on the per-project slug, so re-running only adds new ones.
Importing never broadcasts email — these are historical, not fresh, releases.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Integration, Project, Release, ReleaseStatus
from app.services import github
from app.services.render import render_markdown

log = logging.getLogger("shiplog.importer")

_MAX_TITLE = 255
_MAX_SLUG = 128


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:_MAX_SLUG]


async def import_release_records(
    db, project: Project, records: list[dict]
) -> int:
    """Create PUBLISHED Release rows from release dicts; dedup by slug. Testable
    with synthetic records (no GitHub needed)."""
    existing = set(
        await db.scalars(
            select(Release.slug).where(Release.project_id == project.id)
        )
    )
    created = 0
    for rec in records:
        title = (rec.get("name") or rec.get("tag") or "").strip()
        slug = _slugify(rec.get("tag") or title)
        if not title or not slug or slug in existing:
            continue
        md = (rec.get("body") or "").strip() or f"Release {title}"
        db.add(
            Release(
                project_id=project.id,
                title=title[:_MAX_TITLE],
                slug=slug,
                version=(rec.get("tag") or None),
                body_markdown=md,
                body_html=render_markdown(md),  # sanitize at write time
                status=ReleaseStatus.PUBLISHED,
                published_at=rec.get("published_at") or datetime.now(UTC),
                ai_generated=False,
            )
        )
        existing.add(slug)
        created += 1
    if created:
        await db.commit()
    return created


async def import_from_github_releases(db, project: Project, limit: int = 20) -> int:
    """Pull GitHub Releases across every connected repo and import them."""
    integrations = list(
        await db.scalars(
            select(Integration).where(Integration.project_id == project.id)
        )
    )
    records: list[dict] = []
    for integ in integrations:
        records += await github.list_releases(
            integ.installation_id, integ.repo_full_name, limit=limit
        )
    count = await import_release_records(db, project, records)
    log.info("imported %d prior releases for project %s", count, project.id)
    return count
