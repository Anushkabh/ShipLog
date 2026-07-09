"""Auth + tenancy dependencies — the single data-access choke point (§5).

Row-level multi-tenancy means every scoped query must be constrained to the
caller's project. Rather than sprinkle `WHERE project_id = ...` everywhere, we
resolve it ONCE here: `require_project` proves the current user is a member of
the org that owns the project and hands back the loaded Project. Routers then
trust the injected object.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import (
    Organization,
    OrganizationMember,
    OrgRole,
    Project,
    User,
)
from app.security import COOKIE_NAME, read_session

DbDep = Annotated[AsyncSession, Depends(get_db)]

# Role ordering for "at least this level" checks.
_ROLE_RANK = {
    OrgRole.VIEWER: 0,
    OrgRole.EDITOR: 1,
    OrgRole.ADMIN: 2,
    OrgRole.OWNER: 3,
}


async def current_user(request: Request, db: DbDep) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user_id = read_session(token) if token else None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session user not found")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def _membership(
    db: AsyncSession, user: User, organization_id: str
) -> OrganizationMember:
    row = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if not row:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this org")
    return row


def require_project(min_role: OrgRole = OrgRole.VIEWER):
    """Factory: dependency that loads a path `project_id` and enforces role.

    Usage:
        @router.post("/projects/{project_id}/releases")
        async def create(project: Annotated[Project, Depends(require_project(OrgRole.EDITOR))]):
    """

    async def dep(project_id: str, db: DbDep, user: CurrentUser) -> Project:
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        member = await _membership(db, user, project.organization_id)
        if _ROLE_RANK[member.role] < _ROLE_RANK[min_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Requires {min_role.value} role or higher"
            )
        return project

    return dep


async def user_orgs(db: AsyncSession, user: User) -> list[Organization]:
    return list(
        await db.scalars(
            select(Organization)
            .join(OrganizationMember)
            .where(OrganizationMember.user_id == user.id)
        )
    )
