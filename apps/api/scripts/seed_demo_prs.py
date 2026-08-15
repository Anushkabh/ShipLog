"""Seed a demo project with realistic merged PRs for testing Smart Release.

Idempotent: re-running clears and re-seeds the demo project's ingested items.
The set deliberately mixes user-facing work (features / improvements / fixes)
with chores/refactors/deps/tests/docs that a good draft should OMIT — so we can
judge grouping, user-impact phrasing, and noise-filtering all at once.

Run:  .venv/bin/python scripts/seed_demo_prs.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from eval_cases import CASES, REPO  # golden dataset (shared with the eval runner)
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    IngestedItem,
    IntegrationProvider,
    OrganizationMember,
    Project,
    Release,
    User,
)

DEMO_SLUG = "smart-release-demo"
DEMO_NAME = "Smart Release Demo"


async def main() -> None:
    async with SessionLocal() as db:
        owner = await db.scalar(select(User).where(User.email == "dev@shiplog.app"))
        if not owner:
            raise SystemExit("No dev@shiplog.app user — log in via dev-login once first.")
        membership = await db.scalar(
            select(OrganizationMember).where(OrganizationMember.user_id == owner.id)
        )
        org_id = membership.organization_id

        project = await db.scalar(
            select(Project).where(
                Project.organization_id == org_id, Project.slug == DEMO_SLUG
            )
        )
        if not project:
            project = Project(organization_id=org_id, name=DEMO_NAME, slug=DEMO_SLUG)
            db.add(project)
            await db.flush()

        # Idempotent full reset: wipe prior seed items AND any test releases, so
        # the "since last published release" window starts empty every re-seed.
        await db.execute(
            delete(IngestedItem).where(IngestedItem.project_id == project.id)
        )
        await db.execute(delete(Release).where(Release.project_id == project.id))

        base = datetime.now(UTC) - timedelta(days=len(CASES))
        for i, case in enumerate(CASES):
            db.add(
                IngestedItem(
                    project_id=project.id,
                    provider=IntegrationProvider.GITHUB,
                    external_id=str(case.number),
                    title=case.title,
                    body=case.body,
                    labels=case.labels,
                    author="acme-dev",
                    url=f"https://github.com/{REPO}/pull/{case.number}",
                    merged_at=base + timedelta(days=i),
                )
            )
        await db.commit()

        print(f"Seeded {len(CASES)} merged PRs into project '{project.name}'")
        print(f"  project_id : {project.id}")
        print(f"  public_key : {project.public_key}")
        print(f"  dashboard  : http://localhost:3000/projects/{project.id}/releases")


if __name__ == "__main__":
    asyncio.run(main())
