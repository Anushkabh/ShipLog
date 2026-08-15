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
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from app.config import settings

_API = "https://api.github.com"

# Markdown paths that never carry product context (legal, process, templates,
# vendored trees). CHANGELOG/HISTORY are excluded here — they're voice samples,
# imported separately, not product description.
_DOC_SKIP = re.compile(
    r"(^|/)(license|changelog|history|releases?|code_of_conduct|security|"
    r"contributing|authors|notice|pull_request_template|issue_template)[^/]*$|"
    r"(^|/)(node_modules|vendor|dist|build|\.github|test|tests|__tests__)/",
    re.IGNORECASE,
)
_MAX_DOC_FILE_BYTES = 50_000


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


def _app_headers() -> dict[str, str]:
    """Auth headers for App-level calls (identify as the App itself)."""
    return {
        "Authorization": f"Bearer {_app_jwt()}",
        "Accept": "application/vnd.github+json",
    }


async def installation_token(installation_id: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.post(
            f"{_API}/app/installations/{installation_id}/access_tokens",
            headers=_app_headers(),
        )
        r.raise_for_status()
        return r.json()["token"]


# ── One-click connect: GitHub App installation flow (setup URL) ────────────
#
# The dashboard sends the admin to github.com/apps/<slug>/installations/new;
# GitHub redirects back to our setup URL with an installation_id. From there we
# list the repos the user granted — no manual owner/repo or ID typing.


async def get_app_slug() -> str | None:
    """The App's public slug (for the install URL).

    Prefer the configured value; otherwise ask GitHub (`GET /app`) so operators
    don't have to copy it by hand. Returns None if the App isn't configured.
    """
    if settings.github_app_slug:
        return settings.github_app_slug
    if not settings.github_app_id or not settings.github_app_private_key:
        return None
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(f"{_API}/app", headers=_app_headers())
        r.raise_for_status()
        return r.json().get("slug")


def install_url(slug: str, state: str) -> str:
    """Where the admin is sent to pick repos and install the App."""
    return f"https://github.com/apps/{slug}/installations/new?state={state}"


async def get_installation(installation_id: str) -> dict[str, Any] | None:
    """Confirm an installation exists and belongs to THIS App.

    GitHub warns the setup-URL `installation_id` can be spoofed, so we never
    trust it blindly — this call (authenticated as the App) is the check. The
    signed `state` round-trip is the other half of the defense.
    """
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(
            f"{_API}/app/installations/{installation_id}", headers=_app_headers()
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def _doc_rank(path: str) -> int:
    """Lower = more likely to describe the product. README first, then docs/,
    then other root-level markdown, then everything deeper."""
    name = path.rsplit("/", 1)[-1].lower()
    depth = path.count("/")
    if name.startswith("readme"):
        return 0
    if path.lower().startswith("docs/"):
        return 10 + depth
    if depth == 0:
        return 20  # other root-level .md (OVERVIEW, ARCHITECTURE, ABOUT, …)
    return 40 + depth


async def gather_docs(
    installation_id: str,
    repo_full_name: str,
    *,
    max_files: int = 6,
    max_chars: int = 8000,
) -> str:
    """Collect the most product-relevant markdown across a repo (not just the
    README) into one bounded blob for profile inference.

    Walks the git tree, keeps `.md`/`.markdown` (minus the skip-list and huge
    files), ranks by likely relevance, then fetches top files until a file/char
    budget is hit. Returns "" if nothing usable is found.
    """
    token = await installation_token(installation_id)
    auth = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=20) as http:
        meta = await http.get(f"{_API}/repos/{repo_full_name}", headers=auth)
        if meta.status_code != 200:
            return ""
        branch = meta.json().get("default_branch") or "main"

        tree_resp = await http.get(
            f"{_API}/repos/{repo_full_name}/git/trees/{branch}",
            headers=auth,
            params={"recursive": "1"},
        )
        if tree_resp.status_code != 200:
            return ""
        mds = [
            t
            for t in tree_resp.json().get("tree", [])
            if t.get("type") == "blob"
            and t.get("path", "").lower().endswith((".md", ".markdown"))
            and not _DOC_SKIP.search(t["path"])
            and 0 < (t.get("size") or 0) <= _MAX_DOC_FILE_BYTES
        ]
        mds.sort(key=lambda t: (_doc_rank(t["path"]), len(t["path"])))

        parts: list[str] = []
        total = 0
        raw_headers = {**auth, "Accept": "application/vnd.github.raw+json"}
        for t in mds:
            if len(parts) >= max_files or total >= max_chars:
                break
            fr = await http.get(
                f"{_API}/repos/{repo_full_name}/contents/{quote(t['path'])}",
                headers=raw_headers,
                params={"ref": branch},
            )
            if fr.status_code != 200 or not fr.text.strip():
                continue
            content = fr.text.strip()
            budget = max_chars - total
            if len(content) > budget:
                content = content[:budget] + "…"
            parts.append(f"# File: {t['path']}\n{content}")
            total += len(content)

    return "\n\n".join(parts)


async def list_installation_repos(installation_id: str) -> list[dict[str, Any]]:
    """Every repo the user granted this installation (paginated)."""
    token = await installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    repos: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15) as http:
        page = 1
        while True:
            r = await http.get(
                f"{_API}/installation/repositories",
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            r.raise_for_status()
            batch = r.json().get("repositories", [])
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return repos


async def list_merged_prs(
    installation_id: str, repo_full_name: str, limit: int = 50
) -> list[dict[str, Any]]:
    """The most recently-updated MERGED PRs for a repo (for backfill/sync).

    The list endpoint can't sort by merge time, so we sort by `updated` desc and
    keep merged ones until we hit `limit`. Each dict matches `normalize_pr`'s
    shape so ingestion is identical whether a PR arrives by webhook or backfill.
    """
    token = await installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20) as http:
        page = 1
        while len(out) < limit:
            r = await http.get(
                f"{_API}/repos/{repo_full_name}/pulls",
                headers=headers,
                params={
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 100,
                    "page": page,
                },
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for pr in batch:
                if not pr.get("merged_at"):
                    continue  # closed-without-merge → not shipped
                out.append(_normalize_list_pr(pr))
                if len(out) >= limit:
                    break
            if len(batch) < 100:
                break
            page += 1
    return out


def _normalize_list_pr(pr: dict[str, Any]) -> dict[str, Any]:
    """Normalize a PR from the *list* endpoint (no event wrapper)."""
    return {
        "external_id": str(pr["number"]),
        "title": pr.get("title") or f"PR #{pr['number']}",
        "body": pr.get("body"),
        "labels": [lbl["name"] for lbl in pr.get("labels", [])],
        "author": (pr.get("user") or {}).get("login"),
        "url": pr.get("html_url") or "",
        "merged_at": _parse_ts(pr.get("merged_at")),
    }


async def list_releases(
    installation_id: str, repo_full_name: str, limit: int = 20
) -> list[dict[str, Any]]:
    """A repo's published GitHub Releases (for importing changelog history).

    Skips drafts. Each dict is ready for the importer to turn into a Release row.
    """
    token = await installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(
            f"{_API}/repos/{repo_full_name}/releases",
            headers=headers,
            params={"per_page": min(limit, 100)},
        )
        if r.status_code != 200:
            return []
        out: list[dict[str, Any]] = []
        for rel in r.json():
            if rel.get("draft"):
                continue  # unpublished drafts aren't real changelog entries
            out.append(
                {
                    "tag": rel.get("tag_name") or "",
                    "name": rel.get("name") or rel.get("tag_name") or "",
                    "body": rel.get("body") or "",
                    "published_at": _parse_ts(rel.get("published_at")),
                    "url": rel.get("html_url") or "",
                    "prerelease": bool(rel.get("prerelease")),
                }
            )
            if len(out) >= limit:
                break
        return out


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
