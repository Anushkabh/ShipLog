"""AI release drafting via LiteLLM BYOK (ARCHITECTURE §7).

LiteLLM gives one interface over OpenAI / Anthropic / Gemini / Groq, so users
plug in their own key and we never pay for inference (Groq/Gemini free tiers
cost them nothing either). The import is LAZY — done inside the call, not at
module top-level — so it never bloats the API's cold start; only the AI handler
pays for it.

The prompt turns merged PRs into *customer-facing* notes: user impact not
implementation, chores omitted, grouped under Added / Improved / Fixed. Drafts
are never auto-published — a changelog is a public record and models
hallucinate, so a human always edits first.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.models import AiProvider, IngestedItem

# Sensible free/cheap default model per provider; the user can't pick a model in
# the MVP, we choose a good general one for each.
_DEFAULT_MODEL = {
    AiProvider.OPENAI: "gpt-4o-mini",
    AiProvider.ANTHROPIC: "claude-3-5-haiku-latest",
    AiProvider.GEMINI: "gemini/gemini-2.0-flash",
    AiProvider.GROQ: "groq/llama-3.3-70b-versatile",
}

# The house style: a suggested title + version, a warm intro, highlighted major
# features, then grouped smaller items — modelled on polished changelogs like
# ReleaseNotes.io. The TITLE/VERSION preamble is parsed out by the router and
# emitted as a `meta` SSE event so it can populate the editor's title field.
_SYSTEM = """You are the release-notes writer for a software product. Turn the \
merged pull requests below into ONE polished, customer-facing release note.

OUTPUT FORMAT — follow exactly, in this order:
1. First line: `TITLE: <short benefit-led headline, ~60 chars max>`
2. Second line: `VERSION: <semantic version if the PRs clearly imply one, else leave empty>`
3. A blank line.
4. A warm 1–2 sentence intro paragraph naming the theme of the release. No heading.
5. `## ✨ What's new` — the 1–3 MOST significant user-facing features. For each: a
   bold lead-in naming the feature, then 1–2 sentences on what it does and why it
   helps users. Skip this section only if there are no notable features.
6. `## Improvements` — short bullets for smaller enhancements. Skip if none.
7. `## Fixes` — short bullets for bug fixes. Skip if none.

RULES:
- Describe USER IMPACT and benefits, not implementation details.
- OMIT ENTIRELY: chores, refactors, dependency bumps, CI, tests, and internal or
  docs-only changes. A reader should never see them.
- Keep concrete, verifiable specifics from the PRs (numbers, limits) but never
  invent anything not supported by them.
- Output ONLY the note, starting at the TITLE line. No preamble, no code fences."""


@dataclass
class ReleaseExample:
    """A past published note used as a few-shot voice sample."""

    title: str
    body_markdown: str


@dataclass
class ProductProfile:
    """Product context that grounds the draft so it sounds on-brand."""

    name: str
    summary: str | None = None
    audience: str | None = None
    tone: str | None = None

    def as_block(self) -> str:
        lines = [f"Product name: {self.name}"]
        if self.summary:
            lines.append(f"What it is: {self.summary}")
        if self.audience:
            lines.append(f"Audience (who reads these notes): {self.audience}")
        if self.tone:
            lines.append(f"Desired voice/tone: {self.tone}")
        return "\n".join(lines)


# Keep each PR description bounded so a handful of verbose PRs can't blow the
# context window, but give the model the whole story, not just the first line.
_MAX_BODY_CHARS = 1500
_MAX_EXAMPLE_CHARS = 1200


def _prompt(
    items: list[IngestedItem],
    profile: ProductProfile | None = None,
    examples: list[ReleaseExample] | None = None,
) -> str:
    parts: list[str] = []

    if profile:
        parts.append("PRODUCT CONTEXT (use this to shape voice and framing):\n"
                     + profile.as_block())

    if examples:
        # Few-shot: past notes teach the team's voice better than any instruction.
        sample = ["EXAMPLES of our past release notes — match this voice and shape:"]
        for ex in examples:
            body = ex.body_markdown.strip()
            if len(body) > _MAX_EXAMPLE_CHARS:
                body = body[:_MAX_EXAMPLE_CHARS] + "…"
            sample.append(f"---\n# {ex.title}\n{body}")
        sample.append("---")
        parts.append("\n".join(sample))

    lines = ["MERGED PULL REQUESTS since the last release:\n"]
    for it in items:
        labels = f" [labels: {', '.join(it.labels)}]" if it.labels else ""
        lines.append(f"- #{it.external_id}: {it.title}{labels}")
        if it.body:
            body = it.body.strip()
            if len(body) > _MAX_BODY_CHARS:
                body = body[:_MAX_BODY_CHARS] + "…"
            for line in body.splitlines():
                lines.append(f"    {line}")
    parts.append("\n".join(lines))

    parts.append("Write the release note now, starting with the TITLE line.")
    return "\n\n".join(parts)


async def stream_draft(
    provider: AiProvider,
    api_key: str,
    items: list[IngestedItem],
    *,
    profile: ProductProfile | None = None,
    examples: list[ReleaseExample] | None = None,
) -> AsyncIterator[str]:
    """Yield markdown chunks as the model produces them (for SSE)."""
    import litellm  # lazy: heavy import stays out of the API cold-start path

    response = await litellm.acompletion(
        model=_DEFAULT_MODEL[provider],
        api_key=api_key,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _prompt(items, profile, examples)},
        ],
        stream=True,
        temperature=0.4,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
