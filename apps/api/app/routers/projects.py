"""Project CRUD. A project == one changelog (acme.shiplog.app) + one widget key."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbDep, require_project
from app.models import (
    Integration,
    OrganizationMember,
    OrgRole,
    Project,
)
from app.schemas import ProjectCreate, ProjectOut, ProjectProfileUpdate
from app.services import ai, ai_access, cache, github, importer, onboarding

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ImportResult(BaseModel):
    imported: int


class SetupStatus(BaseModel):
    repos_connected: int
    prs_pending: int      # merged PRs since the last published release
    releases: int
    published: int
    drafts: int           # saved but not yet published
    profile_set: bool
    ai_ready: bool
    public_key: str


class SampleDataResult(BaseModel):
    loaded: int


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


@router.put("/{project_id}/profile", response_model=ProjectOut)
async def update_profile(
    body: ProjectProfileUpdate,
    project: Annotated[Project, Depends(require_project(OrgRole.EDITOR))],
    db: DbDep,
) -> Project:
    """Set the product context that grounds AI drafting (name is the project name)."""
    project.product_summary = (body.product_summary or "").strip() or None
    project.audience = (body.audience or "").strip() or None
    project.tone = (body.tone or "").strip() or None
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/profile/infer", response_model=ProjectProfileUpdate)
async def infer_profile(
    project: Annotated[Project, Depends(require_project(OrgRole.EDITOR))],
    db: DbDep,
) -> ProjectProfileUpdate:
    """Draft the product profile from a connected repo's markdown docs (not saved —
    the caller reviews and PUTs it). Uses the project's key or the built-in one."""
    integrations = list(
        await db.scalars(
            select(Integration).where(Integration.project_id == project.id)
        )
    )
    if not integrations:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Connect a GitHub repo first."
        )
    # Gather product-relevant markdown from the first connected repo that has any.
    docs = ""
    try:
        for integration in integrations:
            docs = await github.gather_docs(
                integration.installation_id, integration.repo_full_name
            )
            if docs:
                break
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't reach GitHub: {str(e)[:120]}"
        ) from None
    if not docs:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "None of the connected repos have markdown docs to analyze.",
        )
    access = await ai_access.require(db, project)  # after docs: never charge for nothing
    result = await ai.infer_profile(
        access.provider, access.api_key, project.name, docs
    )
    return ProjectProfileUpdate(**result)


@router.post("/{project_id}/import/releases", response_model=ImportResult)
async def import_releases(
    project: Annotated[Project, Depends(require_project(OrgRole.EDITOR))],
    db: DbDep,
) -> ImportResult:
    """Import prior release notes from the connected repos' GitHub Releases as
    published history (also seeds the AI's voice examples). Idempotent."""
    integration = await db.scalar(
        select(Integration).where(Integration.project_id == project.id)
    )
    if not integration:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Connect a GitHub repo first."
        )
    try:
        count = await importer.import_from_github_releases(db, project)
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't reach GitHub: {str(e)[:120]}"
        ) from None
    if count:
        await cache.bust_feed(project.public_key)  # new published releases
    return ImportResult(imported=count)


@router.get("/{project_id}/setup", response_model=SetupStatus)
async def setup_status(
    project: Annotated[Project, Depends(require_project(OrgRole.VIEWER))],
    db: DbDep,
) -> SetupStatus:
    """Checklist state for the Get started page (polled while onboarding runs)."""
    return SetupStatus(**await onboarding.setup_status(db, project))


@router.post("/{project_id}/sample-data", response_model=SampleDataResult)
async def load_sample_data(
    project: Annotated[Project, Depends(require_project(OrgRole.EDITOR))],
    db: DbDep,
) -> SampleDataResult:
    """Fill the project with realistic merged PRs so the flow can be tried
    without connecting a repo. Leaves the product context alone so sample data
    never leaks into a project that later connects its real repo."""
    return SampleDataResult(loaded=await onboarding.load_sample_prs(db, project))
