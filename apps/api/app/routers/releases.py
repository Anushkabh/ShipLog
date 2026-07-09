"""Release CRUD + publish. body_html is rendered+sanitized at WRITE time so the
read path (widget feed, public site) never trusts raw input (ARCHITECTURE §7-9)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbDep, require_project
from app.models import (
    OrgRole,
    Project,
    Release,
    ReleaseStatus,
    Tag,
)
from app.schemas import (
    PublishRequest,
    ReleaseCreate,
    ReleaseOut,
    ReleaseUpdate,
)
from app.services import cache
from app.services.publish import publish_release

router = APIRouter(prefix="/api/projects/{project_id}/releases", tags=["releases"])

EditorProject = Annotated[Project, Depends(require_project(OrgRole.EDITOR))]
ViewerProject = Annotated[Project, Depends(require_project(OrgRole.VIEWER))]


async def _load(db, project_id: str, release_id: str) -> Release:
    r = await db.scalar(
        select(Release)
        .where(Release.id == release_id, Release.project_id == project_id)
        .options(selectinload(Release.tags))
    )
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Release not found")
    return r


async def _resolve_tags(db, project_id: str, tag_ids: list[str]) -> list[Tag]:
    if not tag_ids:
        return []
    tags = list(
        await db.scalars(
            select(Tag).where(Tag.id.in_(tag_ids), Tag.project_id == project_id)
        )
    )
    return tags


@router.get("", response_model=list[ReleaseOut])
async def list_releases(project: ViewerProject, db: DbDep) -> list[Release]:
    return list(
        await db.scalars(
            select(Release)
            .where(Release.project_id == project.id)
            .order_by(Release.created_at.desc())
            .options(selectinload(Release.tags))
        )
    )


@router.post("", response_model=ReleaseOut, status_code=status.HTTP_201_CREATED)
async def create_release(
    body: ReleaseCreate, project: EditorProject, user: CurrentUser, db: DbDep
) -> Release:
    from app.services.render import render_markdown

    release = Release(
        project_id=project.id,
        title=body.title,
        slug=body.slug,
        version=body.version,
        body_markdown=body.body_markdown,
        body_html=render_markdown(body.body_markdown),  # sanitize at write time
        status=ReleaseStatus.DRAFT,
        author_id=user.id,
    )
    release.tags = await _resolve_tags(db, project.id, body.tag_ids)
    db.add(release)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Slug already used in this project"
        ) from None
    return await _load(db, project.id, release.id)


@router.get("/{release_id}", response_model=ReleaseOut)
async def get_release(project: ViewerProject, release_id: str, db: DbDep) -> Release:
    return await _load(db, project.id, release_id)


@router.patch("/{release_id}", response_model=ReleaseOut)
async def update_release(
    body: ReleaseUpdate, project: EditorProject, release_id: str, db: DbDep
) -> Release:
    from app.services.render import render_markdown

    release = await _load(db, project.id, release_id)
    if body.title is not None:
        release.title = body.title
    if body.version is not None:
        release.version = body.version
    if body.body_markdown is not None:
        release.body_markdown = body.body_markdown
        release.body_html = render_markdown(body.body_markdown)  # re-sanitize
    if body.tag_ids is not None:
        release.tags = await _resolve_tags(db, project.id, body.tag_ids)
    await db.commit()

    # An edit to an already-published release must invalidate the cached feed.
    if release.status == ReleaseStatus.PUBLISHED:
        await cache.bust_feed(project.public_key)
    return await _load(db, project.id, release_id)


@router.post("/{release_id}/publish", response_model=ReleaseOut)
async def publish(
    body: PublishRequest, project: EditorProject, release_id: str, db: DbDep
) -> Release:
    release = await _load(db, project.id, release_id)

    if body.scheduled_at:
        if body.scheduled_at <= datetime.now(UTC):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "scheduled_at must be future")
        release.status = ReleaseStatus.SCHEDULED
        release.scheduled_at = body.scheduled_at
        await db.commit()
        return await _load(db, project.id, release_id)

    await publish_release(db, project, release, broadcast_email=body.broadcast_email)
    return await _load(db, project.id, release_id)


@router.post("/{release_id}/private-link", response_model=ReleaseOut)
async def make_private(project: EditorProject, release_id: str, db: DbDep) -> Release:
    release = await _load(db, project.id, release_id)
    release.is_private = True
    release.access_token = secrets.token_urlsafe(32)
    await db.commit()
    await cache.bust_feed(project.public_key)  # drop it from the public feed
    return await _load(db, project.id, release_id)


@router.delete("/{release_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release(project: EditorProject, release_id: str, db: DbDep) -> None:
    release = await _load(db, project.id, release_id)
    was_published = release.status == ReleaseStatus.PUBLISHED
    await db.delete(release)
    await db.commit()
    if was_published:
        await cache.bust_feed(project.public_key)
