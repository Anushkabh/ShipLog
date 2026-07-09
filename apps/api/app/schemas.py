"""Request/response shapes. Kept separate from ORM models so the wire format
is an explicit, versioned contract — never leak the DB schema by accident."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import OrgRole, ReleaseStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth / identity ───────────────────────────────────────────────────────
class UserOut(ORMModel):
    id: str
    name: str | None
    email: str
    image: str | None


class OrgOut(ORMModel):
    id: str
    name: str
    slug: str
    role: OrgRole | None = None  # caller's role, filled per-request


# ── Projects ──────────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    organization_id: str


class ProjectOut(ORMModel):
    id: str
    name: str
    slug: str
    public_key: str
    custom_domain: str | None
    domain_verified: bool
    email_enabled: bool
    created_at: datetime


# ── Tags ──────────────────────────────────────────────────────────────────
class TagOut(ORMModel):
    id: str
    name: str
    color: str


# ── Releases ──────────────────────────────────────────────────────────────
class ReleaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    version: str | None = Field(default=None, max_length=64)
    body_markdown: str = ""
    tag_ids: list[str] = []


class ReleaseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=64)
    body_markdown: str | None = None
    tag_ids: list[str] | None = None


class PublishRequest(BaseModel):
    scheduled_at: datetime | None = None   # None = publish now
    broadcast_email: bool = True


class ReleaseOut(ORMModel):
    id: str
    project_id: str
    title: str
    slug: str
    version: str | None
    body_markdown: str
    body_html: str
    status: ReleaseStatus
    is_private: bool
    scheduled_at: datetime | None
    published_at: datetime | None
    ai_generated: bool
    created_at: datetime
    updated_at: datetime
    tags: list[TagOut] = []


# ── Widget feed (contract consumed by packages/widget/widget.js) ──────────
class FeedTag(BaseModel):
    name: str
    color: str


class FeedRelease(BaseModel):
    publishedAt: datetime          # widget reads releases[0].publishedAt as newest
    title: str
    url: str
    bodyHtml: str                  # already sanitized at write time
    tags: list[FeedTag] = []


class WidgetFeed(BaseModel):
    releases: list[FeedRelease]
    siteUrl: str


# ── Subscribers ───────────────────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    email: EmailStr
