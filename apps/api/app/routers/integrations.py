"""GitHub repo connections (ARCHITECTURE §6).

A project connects one or more repos via a GitHub App installation. The webhook
consumer routes incoming merged PRs to a project by matching repo_full_name
here, so this table is the ingestion pipeline's routing map.

In the real flow the installation_id comes from the GitHub App install
redirect; here we accept it directly so the pipeline is testable end-to-end.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import DbDep, require_project
from app.models import Integration, IntegrationProvider, OrgRole, Project
from app.schemas import ORMModel

router = APIRouter(prefix="/api/projects/{project_id}/integrations", tags=["integrations"])

AdminProject = Annotated[Project, Depends(require_project(OrgRole.ADMIN))]
ViewerProject = Annotated[Project, Depends(require_project(OrgRole.VIEWER))]


class IntegrationIn(BaseModel):
    installation_id: str
    repo_full_name: str  # "acme/backend"


class IntegrationOut(ORMModel):
    id: str
    provider: IntegrationProvider
    installation_id: str
    repo_full_name: str


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(project: ViewerProject, db: DbDep):
    return list(
        await db.scalars(
            select(Integration).where(Integration.project_id == project.id)
        )
    )


@router.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
async def connect_repo(body: IntegrationIn, project: AdminProject, db: DbDep):
    integration = Integration(
        project_id=project.id,
        provider=IntegrationProvider.GITHUB,
        installation_id=body.installation_id,
        repo_full_name=body.repo_full_name,
    )
    db.add(integration)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Repo already connected to this project"
        ) from None
    await db.refresh(integration)
    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repo(project: AdminProject, integration_id: str, db: DbDep):
    integration = await db.get(Integration, integration_id)
    if not integration or integration.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")
    await db.delete(integration)
    await db.commit()
