"""One-click demo workspaces: try the whole product with no signup.

`create_demo_workspace` makes a throwaway user + private org + a project for a
fictional product (Acme Analytics) that's already fully set up:
  • product context filled in,
  • two past releases published (so the public changelog and widget aren't
    empty, and the AI has voice examples to match),
  • 18 merged PRs waiting to be drafted.

Each visitor gets their own sandbox, so nobody sees anyone else's edits.
Sandboxes are marked by a `demo-` prefix and deleted after DEMO_TTL_HOURS by
`purge_expired_demos` (run from the scheduler).
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.models import (
    IngestedItem,
    IntegrationProvider,
    Organization,
    OrganizationMember,
    OrgRole,
    Project,
    Release,
    ReleaseStatus,
    User,
)
from app.models import _id as _new_id  # assign PKs up front: no flush needed to link rows
from app.services.render import render_markdown
from app.services.sample_data import CASES, REPO

log = logging.getLogger("shiplog.demo")

DEMO_PREFIX = "demo-"
DEMO_TTL_HOURS = 24

_PAST_RELEASES = [
    {
        "tag": "v2.2.0",
        "name": "Saved dashboards and a faster query engine",
        "published_days_ago": 42,
        "body": (
            "This release is all about getting to your answers faster.\n\n"
            "## ✨ What's new\n"
            "**Saved dashboards** — pin the charts you check every morning into a "
            "dashboard and share it with your team in one click.\n\n"
            "## Improvements\n"
            "* Queries over 90 days of data now return up to 3× faster.\n"
            "* Chart tooltips show exact values and the comparison period.\n\n"
            "## Fixes\n"
            "* Funnels no longer double-count users who revisit a step."
        ),
    },
    {
        "tag": "v2.3.0",
        "name": "Cohorts, CSV imports, and smoother onboarding",
        "published_days_ago": 21,
        "body": (
            "We're excited to share a batch of updates that make it easier to "
            "understand who your users are.\n\n"
            "## ✨ What's new\n"
            "**Cohorts** — group users by sign-up week or behaviour and compare "
            "their retention side by side.\n\n"
            "**CSV imports** — bring in historical events from a spreadsheet, no "
            "engineering help needed.\n\n"
            "## Improvements\n"
            "* The setup checklist now walks new workspaces through their first chart.\n\n"
            "## Fixes\n"
            "* Date pickers respect your workspace's first day of the week."
        ),
    },
]


def is_demo_user(user: User) -> bool:
    return bool(user.github_id and user.github_id.startswith(DEMO_PREFIX))


async def create_demo_workspace(db) -> tuple[User, Project]:
    """Build the whole sandbox in memory and save it in ONE transaction.

    Every round trip counts when the API and database are far apart, so this
    avoids per-row upserts, refreshes, and intermediate commits: the sandbox is
    brand new, so plain batched INSERTs (one per table) are enough.
    """
    token = secrets.token_hex(5)
    now = datetime.now(UTC)

    user = User(
        id=_new_id(),
        github_id=f"{DEMO_PREFIX}{token}",
        name="Demo visitor",
        email=f"{DEMO_PREFIX}{token}@demo.shiplog.invalid",
    )
    org = Organization(id=_new_id(), name="Demo workspace", slug=f"{DEMO_PREFIX}{token}")
    project = Project(
        id=_new_id(),
        public_key=_new_id(),
        organization_id=org.id,
        name="Acme Analytics",
        slug=f"{DEMO_PREFIX}acme-{token}",
        product_summary=(
            "Acme Analytics is a self-serve product-analytics dashboard that helps "
            "SaaS teams track usage, funnels, and revenue."
        ),
        audience="Product managers and founders at SaaS companies",
        tone="Friendly, confident, and concrete — benefit-led, no jargon",
    )
    db.add_all([user, org])
    db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role=OrgRole.OWNER))
    db.add(project)

    # Past releases: published history (public page + widget) and voice examples.
    for r in _PAST_RELEASES:
        db.add(
            Release(
                project_id=project.id,
                title=r["name"],
                slug=r["tag"].replace(".", "-"),
                version=r["tag"],
                body_markdown=r["body"],
                body_html=render_markdown(r["body"]),
                status=ReleaseStatus.PUBLISHED,
                published_at=now - timedelta(days=r["published_days_ago"]),
                ai_generated=False,
            )
        )

    # The merged PRs waiting to be drafted (newest last, all after the last release).
    for i, case in enumerate(CASES):
        db.add(
            IngestedItem(
                project_id=project.id,
                provider=IntegrationProvider.GITHUB,
                external_id=str(case.number),
                title=case.title,
                body=case.body,
                labels=case.labels,
                author="sample-data",
                url=f"https://github.com/{REPO}/pull/{case.number}",
                merged_at=now - timedelta(minutes=10 * (len(CASES) - i)),
            )
        )

    await db.commit()
    log.info("created demo workspace %s", org.slug)
    return user, project


async def purge_expired_demos(db) -> int:
    """Delete demo orgs (cascading to their projects/releases/PRs) and users
    older than the TTL. Returns how many orgs were removed."""
    cutoff = datetime.now(UTC) - timedelta(hours=DEMO_TTL_HOURS)
    org_ids = list(
        await db.scalars(
            select(Organization.id).where(
                Organization.slug.startswith(DEMO_PREFIX),
                Organization.created_at < cutoff,
            )
        )
    )
    if org_ids:
        await db.execute(delete(Organization).where(Organization.id.in_(org_ids)))
    await db.execute(
        delete(User).where(User.github_id.startswith(DEMO_PREFIX), User.created_at < cutoff)
    )
    await db.commit()
    if org_ids:
        log.info("purged %d expired demo workspaces", len(org_ids))
    return len(org_ids)
