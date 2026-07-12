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

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import DbDep, require_project
from app.models import AiCredential, AiProvider, IngestedItem, OrgRole, Project
from app.services import crypto
from app.services.ai import stream_draft

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

    # Unused items = ingested but not yet attached to any release.
    items = list(
        await db.scalars(
            select(IngestedItem)
            .where(
                IngestedItem.project_id == project.id,
                IngestedItem.release_id.is_(None),
            )
            .order_by(IngestedItem.merged_at.desc())
        )
    )
    if not items:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No new merged PRs since the last release"
        )

    api_key = crypto.decrypt(cred.encrypted_key)

    async def sse():
        # SSE frames: "data: <chunk>\n\n". A final [DONE] lets the client close.
        try:
            async for chunk in stream_draft(cred.provider, api_key, items):
                # Escape newlines within a data frame so multi-line markdown
                # survives the SSE line-based protocol.
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n"
        except Exception as e:  # surface provider errors to the editor
            yield f"event: error\ndata: {str(e)[:200]}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
