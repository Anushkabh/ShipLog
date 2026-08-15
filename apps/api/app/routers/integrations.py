"""GitHub repo connections (ARCHITECTURE §6).

A project connects one or more repos via a GitHub App installation. The webhook
consumer routes incoming merged PRs to a project by matching repo_full_name
here, so this table is the ingestion pipeline's routing map.

Connect flow (one-click, no manual IDs):

  GET  …/github/install  → sign an HMAC state, redirect the admin to
                           github.com/apps/<slug>/installations/new
  (user picks repos on GitHub)
  GET  /integrations/github/setup  → GitHub's Setup URL redirects back here with
                           an installation_id; we verify the signed state + the
                           browser cookie + the caller's ADMIN role, then list
                           the granted repos and upsert one Integration each.

The signed state (bound to the project + this browser) is what defends the setup
URL against spoofed installation_ids — GitHub itself warns the raw id is not
trustworthy. The legacy POST endpoint is kept so scripts can wire integrations
directly without a live GitHub App.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.deps import _ROLE_RANK, DbDep, current_user, require_project
from app.models import (
    Integration,
    IntegrationProvider,
    OrganizationMember,
    OrgRole,
    Project,
)
from app.schemas import ORMModel
from app.services import backfill, crypto, github

log = logging.getLogger("shiplog.integrations")

router = APIRouter(prefix="/api/projects/{project_id}/integrations", tags=["integrations"])

# Separate router: GitHub calls this back at a fixed path with no project in the
# URL, so it can't live under the project-scoped prefix above.
setup_router = APIRouter(prefix="/integrations/github", tags=["integrations"])

AdminProject = Annotated[Project, Depends(require_project(OrgRole.ADMIN))]
EditorProject = Annotated[Project, Depends(require_project(OrgRole.EDITOR))]
ViewerProject = Annotated[Project, Depends(require_project(OrgRole.VIEWER))]

_STATE_COOKIE = "shiplog_gh_install_state"

# Strong refs so fire-and-forget backfill tasks aren't garbage-collected.
_backfill_tasks: set[asyncio.Task] = set()


def _fire_backfill(integration_id: str) -> None:
    """Kick off a detached backfill (local dev). Never blocks the caller."""
    task = asyncio.create_task(backfill.run_for_integration(integration_id))
    _backfill_tasks.add(task)
    task.add_done_callback(_backfill_tasks.discard)


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


class SyncResult(BaseModel):
    ingested: int


@router.post("/{integration_id}/sync", response_model=SyncResult)
async def sync_repo(project: EditorProject, integration_id: str, db: DbDep) -> SyncResult:
    """Pull recent merged PRs for a repo on demand (the manual 'Sync' button)."""
    integration = await db.get(Integration, integration_id)
    if not integration or integration.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")
    try:
        count = await backfill.backfill_integration(db, integration)
    except Exception as e:
        log.exception("sync failed for %s", integration.repo_full_name)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't reach GitHub: {str(e)[:120]}"
        ) from None
    return SyncResult(ingested=count)


# ── One-click connect ──────────────────────────────────────────────────────


@router.get("/github/install")
async def github_install(project: AdminProject) -> RedirectResponse:
    """Send the admin to GitHub to install the App and pick repos.

    We mint an HMAC-signed state carrying this project id and mirror it into a
    short-lived cookie; the setup callback checks both, so a stray hit on the
    Setup URL with a forged installation_id can't attach repos to a project.
    """
    slug = await github.get_app_slug()
    if not slug:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "GitHub App is not configured"
        )
    state = crypto.sign(f"{project.id}:{secrets.token_urlsafe(24)}")
    resp = RedirectResponse(github.install_url(slug, state))
    resp.set_cookie(
        _STATE_COOKIE, state, max_age=600, httponly=True,
        secure=settings.is_prod, samesite="lax", path="/",
    )
    return resp


def _dashboard(project_id: str | None, **params: str) -> str:
    q = "&".join(f"{k}={v}" for k, v in params.items())
    base = (
        f"{settings.app_url}/projects/{project_id}/integrations"
        if project_id
        else f"{settings.app_url}/projects"
    )
    return f"{base}?{q}" if q else base


@setup_router.get("/setup")
async def github_setup(request: Request, db: DbDep) -> RedirectResponse:
    """GitHub's Setup URL: land here after the user installs the App.

    Every failure path bounces back to the dashboard with a `gh_error` query
    rather than throwing — this is a browser redirect from github.com, not an
    API call, so a raw 4xx would be a dead end for the user.
    """
    installation_id = request.query_params.get("installation_id")
    state = request.query_params.get("state")

    # 1. State must be present, HMAC-valid, and match the cookie for THIS browser.
    payload = crypto.verify_signed(state) if state else None
    if not payload or state != request.cookies.get(_STATE_COOKIE):
        return RedirectResponse(_dashboard(None, gh_error="state"), status_code=302)
    project_id = payload.split(":", 1)[0]

    resp_err = lambda code: RedirectResponse(  # noqa: E731
        _dashboard(project_id, gh_error=code), status_code=302
    )

    # 2. The caller must be a signed-in admin of the project that started this.
    try:
        user = await current_user(request, db)
    except HTTPException:
        return resp_err("auth")
    project = await db.get(Project, project_id)
    if not project:
        return resp_err("project")
    member = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == project.organization_id,
        )
    )
    if not member or _ROLE_RANK[member.role] < _ROLE_RANK[OrgRole.ADMIN]:
        return resp_err("forbidden")

    # 3. Validate the installation against GitHub (never trust the raw id) and
    #    enumerate the repos the user granted.
    if not installation_id:
        return resp_err("installation")
    try:
        if await github.get_installation(installation_id) is None:
            return resp_err("installation")
        repos = await github.list_installation_repos(installation_id)
    except Exception:
        log.exception("github install callback failed for project %s", project_id)
        return resp_err("github")

    # 4. Upsert one Integration per repo; reconnecting just refreshes the id.
    integration_ids: list[str] = []
    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        row = await db.execute(
            pg_insert(Integration)
            .values(
                project_id=project_id,
                provider=IntegrationProvider.GITHUB,
                installation_id=str(installation_id),
                repo_full_name=full_name,
            )
            .on_conflict_do_update(
                constraint="uq_integration",
                set_={"installation_id": str(installation_id)},
            )
            .returning(Integration.id)
        )
        integration_ids.append(row.scalar_one())
    await db.commit()

    # 5. Backfill recent merged PRs in the background so material shows up
    #    without waiting for the next webhook. Detached — connect returns now.
    for iid in integration_ids:
        _fire_backfill(iid)

    ok = RedirectResponse(
        _dashboard(project_id, connected=str(len(integration_ids))), status_code=302
    )
    ok.delete_cookie(_STATE_COOKIE, path="/")
    return ok
