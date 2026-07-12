"""GitHub integration primitives (ARCHITECTURE §6).

Two responsibilities:
  1. Verify inbound webhook signatures in constant time (defends against timing
     attacks — the reason we use hmac.compare_digest, say it out loud).
  2. Mint GitHub App installation tokens (App JWT -> installation access token)
     for pulling PRs on demand, e.g. backfilling merged PRs when a release is
     generated rather than waiting for future webhooks.

We use a GitHub App (not an OAuth app): per-repo install, narrow read-only
scope, its own rate limits, survives the installing employee leaving.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any

import httpx
import jwt

from app.config import settings

_API = "https://api.github.com"


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 in constant time.

    Header format: "sha256=<hex>". Missing secret or header => reject.
    """
    if not settings.github_webhook_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.github_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def _app_jwt() -> str:
    """Short-lived RS256 JWT identifying the GitHub App itself."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": settings.github_app_id}
    return jwt.encode(payload, settings.github_app_private_key, algorithm="RS256")


async def installation_token(installation_id: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.post(
            f"{_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {_app_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        r.raise_for_status()
        return r.json()["token"]


def normalize_pr(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Turn a `pull_request` webhook payload into an ingested-item dict.

    Returns None for anything that isn't a MERGED PR — we only surface shipped
    work in a changelog, not every closed/opened PR.
    """
    if payload.get("action") != "closed":
        return None
    pr = payload.get("pull_request") or {}
    if not pr.get("merged"):
        return None  # closed-without-merge => not shipped => ignore

    return {
        "external_id": str(pr["number"]),
        "title": pr.get("title") or f"PR #{pr['number']}",
        "body": pr.get("body"),
        "labels": [lbl["name"] for lbl in pr.get("labels", [])],
        "author": (pr.get("user") or {}).get("login"),
        "url": pr.get("html_url") or "",
        "merged_at": _parse_ts(pr.get("merged_at")),
        "repo_full_name": (payload.get("repository") or {}).get("full_name"),
    }


def _parse_ts(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))
