"""GitHub OAuth login → JWT session cookie (ARCHITECTURE §4, §9).

Flow: /auth/github/login redirects to GitHub → user authorizes → GitHub calls
/auth/github/callback with a code → we exchange it for an access token, read the
profile, upsert a User (+ a personal Organization on first login), then set the
httpOnly session cookie and bounce to the dashboard.

A local-only /auth/dev-login shortcut lets you exercise the whole product loop
before GitHub OAuth credentials exist. It is a hard 404 outside env=local.
"""

from __future__ import annotations

import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.deps import CurrentUser, DbDep
from app.models import Organization, OrganizationMember, OrgRole, User
from app.schemas import OrgOut, UserOut
from app.security import clear_session_cookie, issue_session, set_session_cookie

router = APIRouter(prefix="/auth", tags=["auth"])

_GH_AUTHORIZE = "https://github.com/login/oauth/authorize"
_GH_TOKEN = "https://github.com/login/oauth/access_token"
_GH_USER = "https://api.github.com/user"
_GH_EMAILS = "https://api.github.com/user/emails"
_OAUTH_STATE_COOKIE = "shiplog_oauth_state"


async def _upsert_user(
    db, *, github_id: str, name: str | None, email: str, image: str | None
) -> User:
    user = await db.scalar(select(User).where(User.github_id == github_id))
    if user is None:
        # Fall back to email match (e.g. they logged in another way before).
        user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(github_id=github_id, name=name, email=email, image=image)
        db.add(user)
        await db.flush()
        # Every user gets a personal org they own — projects hang off orgs.
        org = Organization(name=f"{name or email}'s workspace", slug=_slugify(email))
        db.add(org)
        await db.flush()
        db.add(
            OrganizationMember(
                user_id=user.id, organization_id=org.id, role=OrgRole.OWNER
            )
        )
    else:
        user.github_id = user.github_id or github_id
        user.name = name or user.name
        user.image = image or user.image
    await db.commit()
    return user


def _slugify(email: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in email.split("@")[0].lower())
    return f"{base}-{secrets.token_hex(3)}"


@router.get("/github/login")
async def github_login() -> RedirectResponse:
    if not settings.github_client_id:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "GitHub OAuth not configured")
    state = secrets.token_urlsafe(24)
    url = (
        f"{_GH_AUTHORIZE}?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.api_url}/auth/github/callback"
        f"&scope=read:user user:email&state={state}"
    )
    resp = RedirectResponse(url)
    # Bind the state to this browser to defend the callback against CSRF.
    resp.set_cookie(
        _OAUTH_STATE_COOKIE, state, max_age=600, httponly=True,
        secure=settings.is_prod, samesite="lax", path="/",
    )
    return resp


@router.get("/github/callback")
async def github_callback(request: Request, code: str, state: str, db: DbDep):
    if state != request.cookies.get(_OAUTH_STATE_COOKIE):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")

    async with httpx.AsyncClient(timeout=10) as http:
        tok = await http.post(
            _GH_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{settings.api_url}/auth/github/callback",
            },
        )
        access = tok.json().get("access_token")
        if not access:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token exchange failed")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/json"}
        profile = (await http.get(_GH_USER, headers=headers)).json()
        email = profile.get("email")
        if not email:  # GitHub hides email by default → fetch the primary one
            emails = (await http.get(_GH_EMAILS, headers=headers)).json()
            primary = next(
                (e for e in emails if e.get("primary") and e.get("verified")), None
            )
            email = primary["email"] if primary else f"{profile['id']}@users.noreply.github.com"

    user = await _upsert_user(
        db,
        github_id=str(profile["id"]),
        name=profile.get("name") or profile.get("login"),
        email=email,
        image=profile.get("avatar_url"),
    )
    resp = RedirectResponse(settings.app_url, status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(_OAUTH_STATE_COOKIE, path="/")
    set_session_cookie(resp, issue_session(user.id))
    return resp


@router.post("/dev-login")
async def dev_login(db: DbDep, email: str = "dev@shiplog.app", name: str = "Dev User"):
    """Local-only: mint a session without GitHub. 404 anywhere but env=local."""
    if settings.env != "local":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = await _upsert_user(
        db, github_id=f"dev-{email}", name=name, email=email, image=None
    )
    resp = Response(status_code=204)
    set_session_cookie(resp, issue_session(user.id))
    return resp


@router.post("/logout")
async def logout() -> Response:
    resp = Response(status_code=204)
    clear_session_cookie(resp)
    return resp


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.get("/me/orgs", response_model=list[OrgOut])
async def my_orgs(user: CurrentUser, db: DbDep) -> list[OrgOut]:
    # One query: every org the user belongs to, with their role, via the join.
    rows = await db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
    )
    out = []
    for org, role in rows.all():
        o = OrgOut.model_validate(org)
        o.role = role
        out.append(o)
    return out
