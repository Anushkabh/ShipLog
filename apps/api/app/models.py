"""
Shiplog data model — SQLAlchemy 2.0 (async) + PostgreSQL (Neon).

Direct translation of the original design: multi-tenancy, GitHub ingestion
with two idempotency layers, BYOK AI credentials, email broadcasts with
per-recipient audit rows, hashed API keys, analytics rollups.

Migrations: managed with Alembic (`alembic revision --autogenerate`).
Connect through Neon's POOLED endpoint from Lambda (see ARCHITECTURE §4).
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


# ─────────────────────────── Identity & Tenancy ───────────────────────────


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    image: Mapped[str | None] = mapped_column(String(1024))
    github_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    memberships: Mapped[list[OrganizationMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_member_user_org"),
        Index("ix_member_org", "organization_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    role: Mapped[OrgRole] = mapped_column(
        Enum(OrgRole, name="org_role"), default=OrgRole.EDITOR
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="members")


# ───────────────────────────────── Projects ───────────────────────────────


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_project_org", "organization_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # acme → acme.shiplog.app
    custom_domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    domain_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    public_key: Mapped[str] = mapped_column(  # widget identifier — NOT a secret
        String(32), unique=True, default=_id, index=True
    )
    theme: Mapped[dict | None] = mapped_column(JSON)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    organization: Mapped[Organization] = relationship(back_populates="projects")
    releases: Mapped[list[Release]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


# ───────────────────────────────── Releases ───────────────────────────────


class ReleaseStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_release_project_slug"),
        # Feed + public site query: newest published first, per project.
        Index("ix_release_feed", "project_id", "status", "published_at"),
        # Scheduler cron query: WHERE status='scheduled' AND scheduled_at <= now()
        Index("ix_release_scheduler", "status", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128))  # "v2-4-0", unique per project
    version: Mapped[str | None] = mapped_column(String(64))  # freeform "2.4.0"
    body_markdown: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)  # rendered + nh3-sanitized at WRITE time
    status: Mapped[ReleaseStatus] = mapped_column(
        Enum(ReleaseStatus, name="release_status"), default=ReleaseStatus.DRAFT
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    access_token: Mapped[str | None] = mapped_column(  # signed-link token for private
        String(64), unique=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[str | None] = mapped_column(String(32))  # loose ref, survives user deletion
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="releases")
    tags: Mapped[list[Tag]] = relationship(
        secondary="release_tags", back_populates="releases"
    )
    items: Mapped[list[IngestedItem]] = relationship(back_populates="release")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_tag_project_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))  # "New", "Fixed", "Improved"
    color: Mapped[str] = mapped_column(String(16), default="#6366f1")

    releases: Mapped[list[Release]] = relationship(
        secondary="release_tags", back_populates="tags"
    )


class ReleaseTag(Base):
    __tablename__ = "release_tags"

    release_id: Mapped[str] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (
        # One reaction per emoji per anonymous visitor.
        UniqueConstraint("release_id", "emoji", "visitor_id", name="uq_reaction"),
        Index("ix_reaction_release", "release_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    release_id: Mapped[str] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE")
    )
    emoji: Mapped[str] = mapped_column(String(16))  # "👍" | "❤️" | "🎉"
    visitor_id: Mapped[str] = mapped_column(String(64))  # anonymous hash from widget
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ──────────────────────── GitHub Ingestion Pipeline ───────────────────────


class IntegrationProvider(str, enum.Enum):
    GITHUB = "github"


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "provider", "repo_full_name", name="uq_integration"
        ),
        Index("ix_integration_installation", "installation_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        Enum(IntegrationProvider, name="integration_provider"),
        default=IntegrationProvider.GITHUB,
    )
    installation_id: Mapped[str] = mapped_column(String(64))  # GitHub App installation
    repo_full_name: Mapped[str] = mapped_column(String(255))  # "acme/backend"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebhookEvent(Base):
    """Raw webhook receipts — IDEMPOTENCY LAYER 1.

    GitHub redelivers on timeout; the unique delivery_id constraint makes
    the insert fail fast on a retry instead of double-processing.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (Index("ix_webhook_unprocessed", "processed", "received_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    delivery_id: Mapped[str] = mapped_column(  # X-GitHub-Delivery header
        String(64), unique=True
    )
    event: Mapped[str] = mapped_column(String(64))  # "pull_request"
    action: Mapped[str | None] = mapped_column(String(64))  # "closed"
    payload: Mapped[dict] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngestedItem(Base):
    """Normalized merged PRs that feed AI drafting — IDEMPOTENCY LAYER 2.

    SQS is at-least-once delivery, so the consumer UPSERTs on
    (project_id, provider, external_id); reprocessing is harmless.
    """

    __tablename__ = "ingested_items"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "provider", "external_id", name="uq_ingested_item"
        ),
        # "Unused items since last release" query.
        Index("ix_ingested_unused", "project_id", "release_id", "merged_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        Enum(IntegrationProvider, name="integration_provider", create_type=False),
        default=IntegrationProvider.GITHUB,
    )
    external_id: Mapped[str] = mapped_column(String(64))  # PR number as string
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    author: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    release_id: Mapped[str | None] = mapped_column(  # set once used in a release
        ForeignKey("releases.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    release: Mapped[Release | None] = relationship(back_populates="items")


# ───────────────────────────── AI (BYOK) ──────────────────────────────────


class AiProvider(str, enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"


class AiCredential(Base):
    __tablename__ = "ai_credentials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    provider: Mapped[AiProvider] = mapped_column(Enum(AiProvider, name="ai_provider"))
    # AES-256-GCM: "{iv}.{ciphertext}.{auth_tag}", master key in env only.
    encrypted_key: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ─────────────────────────── Email Distribution ───────────────────────────


class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("project_id", "email", name="uq_subscriber_project_email"),
        Index("ix_subscriber_verified", "project_id", "verified"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(320))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # double opt-in
    verify_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    unsub_token: Mapped[str] = mapped_column(  # embedded in HMAC-signed unsub link
        String(64), unique=True, default=_id
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BroadcastStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class EmailBroadcast(Base):
    __tablename__ = "email_broadcasts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    release_id: Mapped[str] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus, name="broadcast_status"), default=BroadcastStatus.QUEUED
    )
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RecipientStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class EmailRecipient(Base):
    __tablename__ = "email_recipients"
    __table_args__ = (
        # An SQS batch retry can never email the same person twice.
        UniqueConstraint("broadcast_id", "subscriber_id", name="uq_recipient"),
        Index("ix_recipient_status", "broadcast_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    broadcast_id: Mapped[str] = mapped_column(
        ForeignKey("email_broadcasts.id", ondelete="CASCADE")
    )
    subscriber_id: Mapped[str] = mapped_column(
        ForeignKey("subscribers.id", ondelete="CASCADE")
    )
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, name="recipient_status"), default=RecipientStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ──────────────────────────── Public API Keys ─────────────────────────────


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_apikey_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(  # SHA-256 of "slk_..."; raw shown ONCE
        String(64), unique=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ────────────────────────────── Analytics ─────────────────────────────────


class ReleaseViewDaily(Base):
    """Daily rollups flushed from Upstash Redis counters by the EventBridge cron."""

    __tablename__ = "release_views_daily"
    __table_args__ = (
        UniqueConstraint("release_id", "date", name="uq_view_release_date"),
        Index("ix_views_project_date", "project_id", "date"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    release_id: Mapped[str] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date)
    views: Mapped[int] = mapped_column(Integer, default=0)
