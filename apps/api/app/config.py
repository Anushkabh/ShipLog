"""Runtime configuration.

One typed settings object, loaded from environment (Lambda config in prod,
`.env` locally). Nothing secret is ever hardcoded; secrets live only in the
environment. See ARCHITECTURE §9.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Environment ──────────────────────────────────────────────────────
    env: str = "local"  # local | prod
    debug: bool = True

    # ── URLs (used for OAuth redirects, email links, CORS) ───────────────
    app_url: str = "http://localhost:3000"   # dashboard origin (Next.js)
    api_url: str = "http://localhost:8000"   # this API's public origin
    root_domain: str = "shiplog.app"         # tenant subdomains live under this

    # ── Database ─────────────────────────────────────────────────────────
    # Local: docker-compose postgres. Prod: Neon POOLED (PgBouncer) endpoint.
    database_url: str = (
        "postgresql+asyncpg://shiplog:shiplog@localhost:5432/shiplog"
    )

    # ── Redis (cache / rate-limit / view counters) ───────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Secrets ──────────────────────────────────────────────────────────
    # JWT signing key for session cookies. Override in every real env.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days

    # 32-byte master key (base64 or hex) for AES-256-GCM BYOK encryption.
    # In prod this is the ONLY place the master key exists (Lambda env).
    encryption_key: str = "dev-insecure-32byte-master-key!!"

    # ── GitHub OAuth (login) + GitHub App (ingestion) ────────────────────
    github_client_id: str = ""
    github_client_secret: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""       # PEM
    github_webhook_secret: str = ""        # HMAC secret for X-Hub-Signature-256

    # ── Email (SES in prod; console in local) ────────────────────────────
    email_from: str = "Shiplog <updates@shiplog.app>"
    email_backend: str = "console"         # console | ses | resend
    resend_api_key: str = ""

    # ── Queue (SQS in prod; in-process worker locally) ───────────────────
    queue_backend: str = "local"           # local | sqs
    sqs_webhook_url: str = ""
    sqs_email_url: str = ""
    sqs_ai_url: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def cookie_domain(self) -> str | None:
        # Local dev: host-only cookie. Prod: share across *.shiplog.app.
        return None if self.env == "local" else f".{self.root_domain}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
