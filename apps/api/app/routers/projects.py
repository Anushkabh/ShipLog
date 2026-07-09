"""Project CRUD. A project == one changelog (acme.shiplog.app) + one widget key."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbDep, require_project
from app.models import OrganizationMember, OrgRole, Project
from app.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, db: DbDep) -> list[Project]:
    # Only projects in orgs the caller belongs to.
    return list(
        await db.scalars(
            select(Project)
            .join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(Project.created_at.desc())
        )
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, user: CurrentUser, db: DbDep) -> Project:
    # Must be at least editor in the target org.
    member = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == body.organization_id,
        )
    )
    if not member or member.role == OrgRole.VIEWER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Need editor role in this org")

    project = Project(
        name=body.name, slug=body.slug, organization_id=body.organization_id
    )
    db.add(project)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken") from None
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project: Annotated[Project, Depends(require_project(OrgRole.VIEWER))],
) -> Project:
    return project
