"""Public widget endpoints — served under /api/v1/widget/{public_key}/...

This is the exact contract packages/widget/widget.js consumes:
  GET  feed  -> { releases: [{ publishedAt, title, url, bodyHtml, tags[] }], siteUrl }
             ordered NEWEST-FIRST (widget treats releases[0] as newest).
  POST view  -> fire-and-forget analytics increment.

No auth: public_key is a non-secret widget identifier. Feed is Redis-cached so
a million visitors cost ~nothing. bodyHtml is already sanitized at write time,
so we serve it verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DbDep
from app.models import Project, Release, ReleaseStatus
from app.schemas import FeedRelease, FeedTag, WidgetFeed
from app.services import cache

router = APIRouter(prefix="/api/v1/widget", tags=["widget"])

_FEED_LIMIT = 20
# The widget is cross-origin (runs on customer sites) → permissive CORS + a
# short edge cache with stale-while-revalidate for the CDN in front of Lambda.
_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
}


def _site_url(project: Project) -> str:
    from app.config import settings

    if project.custom_domain and project.domain_verified:
        return f"https://{project.custom_domain}"
    return f"https://{project.slug}.{settings.root_domain}"


async def _build_feed(db, project: Project) -> WidgetFeed:
    rows = list(
        await db.scalars(
            select(Release)
            .where(
                Release.project_id == project.id,
                Release.status == ReleaseStatus.PUBLISHED,
                Release.is_private.is_(False),
            )
            .order_by(Release.published_at.desc())
            .limit(_FEED_LIMIT)
            .options(selectinload(Release.tags))
        )
    )
    site = _site_url(project)
    releases = [
        FeedRelease(
            publishedAt=r.published_at,
            title=r.title,
            url=f"{site}/{r.slug}",
            bodyHtml=r.body_html,
            tags=[FeedTag(name=t.name, color=t.color) for t in r.tags],
        )
        for r in rows
    ]
    return WidgetFeed(releases=releases, siteUrl=site)


@router.get("/{public_key}/feed")
async def feed(public_key: str, db: DbDep) -> Response:
    cached = await cache.get_feed(public_key)
    if cached is not None:
        return Response(cached, media_type="application/json", headers=_CORS)

    project = await db.scalar(select(Project).where(Project.public_key == public_key))
    if not project:
        # Don't leak existence; return an empty feed so the widget stays silent.
        empty = WidgetFeed(releases=[], siteUrl="#").model_dump_json()
        return Response(empty, media_type="application/json", headers=_CORS)

    payload = (await _build_feed(db, project)).model_dump_json()
    await cache.set_feed(public_key, payload)
    return Response(payload, media_type="application/json", headers=_CORS)


@router.post("/{public_key}/view/{release_id}")
async def track_view(public_key: str, release_id: str) -> Response:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    await cache.incr_view(release_id, day)  # Redis only; cron flushes to Postgres
    return Response(status_code=204, headers=_CORS)


@router.options("/{rest:path}")
async def preflight(rest: str) -> Response:
    return Response(
        status_code=204,
        headers={**_CORS, "Access-Control-Allow-Methods": "GET, POST, OPTIONS"},
    )
