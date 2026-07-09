"""End-to-end smoke test of the Phase-0/1 product loop, no browser needed.

Exercises: dev-login -> list orgs -> create project -> create release ->
publish (fires the local email consumer) -> fetch the widget feed and assert
it matches the contract packages/widget/widget.js consumes.

Run against a live local stack:
    docker compose up -d db redis
    .venv/bin/alembic upgrade head        # or create_all below on first run
    .venv/bin/python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import sys

import httpx

BASE = "http://localhost:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as c:
        # 1. Dev login — sets the session cookie on the client jar.
        r = await c.post("/auth/dev-login", params={"email": "founder@acme.dev"})
        assert r.status_code == 204, r.text
        me = (await c.get("/auth/me")).json()
        print("logged in as:", me["email"])

        orgs = (await c.get("/auth/me/orgs")).json()
        org_id = orgs[0]["id"]
        print("org:", orgs[0]["slug"], orgs[0]["role"])

        # 2. Create a project (unique slug each run via a counter file-free hash).
        slug = "acme-" + me["id"][:6]
        r = await c.post(
            "/api/projects",
            json={"name": "Acme", "slug": slug, "organization_id": org_id},
        )
        if r.status_code == 409:
            # already exists from a prior run — find it
            projects = (await c.get("/api/projects")).json()
            project = next(p for p in projects if p["slug"] == slug)
        else:
            assert r.status_code == 201, r.text
            project = r.json()
        pid, pubkey = project["id"], project["public_key"]
        print("project:", project["slug"], "| public_key:", pubkey)

        # 3. Create a release with markdown -> sanitized HTML at write time.
        rel_slug = "v1-0-" + me["id"][:4]
        md = "## Highlights\n\n- Ship faster\n- <script>alert(1)</script> should be stripped"
        r = await c.post(
            f"/api/projects/{pid}/releases",
            json={"title": "v1.0", "slug": rel_slug, "body_markdown": md},
        )
        assert r.status_code in (201, 409), r.text
        if r.status_code == 409:
            rel = next(
                x for x in (await c.get(f"/api/projects/{pid}/releases")).json()
                if x["slug"] == rel_slug
            )
        else:
            rel = r.json()
        assert "<script>" not in rel["body_html"], "XSS not sanitized!"
        print("release:", rel["slug"], "| html sanitized:", "<script>" not in rel["body_html"])

        # 4. Publish it (fires local email fan-out consumer).
        r = await c.post(
            f"/api/projects/{pid}/releases/{rel['id']}/publish",
            json={"broadcast_email": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "published"
        print("published at:", r.json()["published_at"])

        # 5. Fetch the widget feed — the exact contract widget.js reads.
        feed = (await c.get(f"/api/v1/widget/{pubkey}/feed")).json()
        assert feed["releases"], "feed empty after publish"
        newest = feed["releases"][0]
        assert {"publishedAt", "title", "url", "bodyHtml", "tags"} <= newest.keys()
        print("feed newest:", newest["title"], "| siteUrl:", feed["siteUrl"])
        print("\n✅ SMOKE PASSED — full product loop works end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
