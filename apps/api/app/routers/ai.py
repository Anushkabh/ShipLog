"""AI settings + release drafting (ARCHITECTURE §7).

- PUT  credential : store the BYOK provider key, AES-256-GCM encrypted at rest.
- GET  credential : report which provider is configured (never returns the key).
- POST generate   : collect unused ingested_items since the last release and
                    stream an AI draft back over SSE (Server-Sent Events).

Streaming through a Lambda Function URL requires response-streaming mode; locally
uvicorn streams natively. The draft is returned to the editor, never
auto-saved — a human edits and publishes.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import DbDep, require_project
from app.models import (
    AiCredential,
    AiProvider,
    IngestedItem,
    OrgRole,
    Project,
    Release,
    ReleaseStatus,
)
from app.services import crypto
from app.services.ai import ProductProfile, ReleaseExample, stream_draft

router = APIRouter(prefix="/api/projects/{project_id}/ai", tags=["ai"])

EditorProject = Annotated[Project, Depends(require_project(OrgRole.EDITOR))]
AdminProject = Annotated[Project, Depends(require_project(OrgRole.ADMIN))]


class CredentialIn(BaseModel):
    provider: AiProvider
    api_key: str


class CredentialStatus(BaseModel):
    configured: bool
    provider: AiProvider | None = None


@router.put("/credential", response_model=CredentialStatus)
async def set_credential(body: CredentialIn, project: AdminProject, db: DbDep):
    existing = await db.scalar(
        select(AiCredential).where(AiCredential.project_id == project.id)
    )
    encrypted = crypto.encrypt(body.api_key)  # AES-256-GCM before it hits Postgres
    if existing:
        existing.provider = body.provider
        existing.encrypted_key = encrypted
    else:
        db.add(
            AiCredential(
                project_id=project.id, provider=body.provider, encrypted_key=encrypted
            )
        )
    await db.commit()
    return CredentialStatus(configured=True, provider=body.provider)


@router.get("/credential", response_model=CredentialStatus)
async def get_credential(project: EditorProject, db: DbDep):
    cred = await db.scalar(
        select(AiCredential).where(AiCredential.project_id == project.id)
    )
    if not cred:
        return CredentialStatus(configured=False)
    return CredentialStatus(configured=True, provider=cred.provider)


@router.post("/generate")
async def generate(project: EditorProject, db: DbDep):
    cred = await db.scalar(
        select(AiCredential).where(AiCredential.project_id == project.id)
    )
    if not cred:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No AI provider configured for this project"
        )

    # "Since the last release" = PRs merged after the most recent PUBLISHED
    # release. Time-based (not a used/unused flag) so it stays correct even if a
    # draft is discarded, and matches how the product is described: everything
    # since you last published. No published release yet → everything so far.
    last_published_at = await db.scalar(
        select(Release.published_at)
        .where(
            Release.project_id == project.id,
            Release.status == ReleaseStatus.PUBLISHED,
            Release.published_at.is_not(None),
        )
        .order_by(Release.published_at.desc())
        .limit(1)
    )
    q = select(IngestedItem).where(IngestedItem.project_id == project.id)
    if last_published_at is not None:
        q = q.where(IngestedItem.merged_at > last_published_at)
    items = list(await db.scalars(q.order_by(IngestedItem.merged_at.desc())))
    if not items:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No new merged PRs since the last release"
        )

    api_key = crypto.decrypt(cred.encrypted_key)

    # Product context (grounds voice) + the last couple of published notes as
    # few-shot voice samples, so drafts sound on-brand instead of generic.
    profile = ProductProfile(
        name=project.name,
        summary=project.product_summary,
        audience=project.audience,
        tone=project.tone,
    )
    example_rows = list(
        await db.scalars(
            select(Release)
            .where(
                Release.project_id == project.id,
                Release.status == ReleaseStatus.PUBLISHED,
            )
            .order_by(Release.published_at.desc())
            .limit(2)
        )
    )
    examples = [
        ReleaseExample(title=r.title, body_markdown=r.body_markdown)
        for r in example_rows
        if (r.body_markdown or "").strip()
    ]

    def _body_frame(text: str) -> str:
        # Escape newlines so multi-line markdown survives the line-based SSE
        # protocol; the client reverses it.
        return f"data: {text.replace(chr(10), chr(92) + 'n')}\n\n"

    async def sse():
        # The model emits a `TITLE:`/`VERSION:` preamble first; we peel those
        # lines off and send them as one `meta` frame so the editor can fill its
        # title/version fields, then stream the note body as `data` frames.
        in_meta = True
        buf = ""
        meta = {"title": "", "version": ""}
        try:
            async for chunk in stream_draft(
                cred.provider, api_key, items,
                profile=profile, examples=examples or None,
            ):
                if not in_meta:
                    if chunk:
                        yield _body_frame(chunk)
                    continue
                buf += chunk
                while "\n" in buf:
                    line, _, rest = buf.partition("\n")
                    up = line.strip().upper()
                    if up.startswith("TITLE:"):
                        meta["title"] = line.split(":", 1)[1].strip()
                        buf = rest
                        continue
                    if up.startswith("VERSION:"):
                        meta["version"] = line.split(":", 1)[1].strip()
                        buf = rest
                        continue
                    if line.strip() == "":
                        buf = rest  # separator between preamble and body
                        continue
                    # First real body line → close the preamble.
                    in_meta = False
                    yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
                    body = line + "\n" + rest
                    buf = ""
                    if body:
                        yield _body_frame(body)
                    break
            if in_meta:  # stream ended inside the preamble (no body line seen)
                yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
                if buf.strip():
                    yield _body_frame(buf)
        except Exception as e:  # surface provider errors to the editor
            yield f"event: error\ndata: {str(e)[:200]}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
