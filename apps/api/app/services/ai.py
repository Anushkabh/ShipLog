"""AI release drafting via LiteLLM BYOK (ARCHITECTURE §7).

LiteLLM gives one interface over OpenAI / Anthropic / Gemini / Groq, so users
plug in their own key and we never pay for inference (Groq/Gemini free tiers
cost them nothing either). The import is LAZY — done inside the call, not at
module top-level — so it never bloats the API's cold start; only the AI handler
pays for it.

Drafting is a two-step pipeline, not one freeform prompt:

  1. classify_prs  — read each PR (title AND body), tag it feature/improvement/
     fix/omit, and distil a clean customer-facing summary. Reading the body (not
     just the title) catches features hidden behind chore-y titles; distilling
     means embedded chores never reach the writer.
  2. stream draft  — omits are filtered in CODE (guaranteed, not hoped-for), then
     the note is streamed from the clean, pre-grouped summaries.

Decomposing this way makes coverage and noise-filtering reliable and testable
(see services/draft_eval.py). Drafts are never auto-published — a changelog is a
public record and models hallucinate, so a human always edits first.
"""

from __future__ import annotations

import json
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

# ── Step 1: triage ─────────────────────────────────────────────────────────
_CLASSIFY_SYSTEM = """You are triaging merged pull requests for a customer-facing \
release note. For EACH pull request, output a classification.

kind — exactly one of:
- "feature"     : a new user-facing capability.
- "improvement" : an enhancement to something that already exists (perf, UX, limits).
- "fix"         : a bug fix users would notice.
- "omit"        : chores, refactors, dependency bumps, CI, tests, and internal or
                  docs-only changes a customer should NEVER see.

CRITICAL: judge by real USER IMPACT, reading the BODY, not just the title.
- A PR titled like a refactor may still ship a user-facing feature — classify it by
  what users get, not the title word.
- A PR titled "Add ..." may be pure dev-tooling — that is still "omit".

summary — for feature/improvement/fix: ONE clean, customer-facing sentence describing
the benefit. No implementation detail, no PR numbers. KEEP concrete specifics
(numbers, limits, percentages). If a PR bundles a user-facing change AND internal
chores, summarise ONLY the user-facing part. For "omit", use an empty string.

Respond with ONLY a JSON array — one object per PR, same order as given:
[{"number": <int>, "kind": "feature|improvement|fix|omit", "summary": "<text>"}]
No prose, no code fences."""

# ── Step 2: write ──────────────────────────────────────────────────────────
# The house style: title + version, a warm intro, highlighted features, then
# grouped smaller items — modelled on polished changelogs like ReleaseNotes.io.
# The TITLE/VERSION preamble is parsed out by the router and emitted as a `meta`
# SSE event so it can populate the editor's title field. Input here is already
# triaged and distilled, so this step is pure writing.
_DRAFT_SYSTEM = """You are the release-notes writer for a software product. You are \
given pre-triaged, already-clean change summaries grouped by type. Turn them into ONE \
polished, customer-facing release note.

OUTPUT FORMAT — follow exactly, in this order:
1. First line: `TITLE: <short benefit-led headline, ~60 chars max>`
2. Second line: `VERSION: <semantic version if clearly implied, else leave empty>`
3. A blank line.
4. A warm 1–2 sentence intro paragraph naming the theme of the release. No heading.
5. `## ✨ What's new` — the Features, most significant first. For each: a bold lead-in
   naming it, then 1–2 sentences on what it does and why it helps. Skip if no features.
6. `## Improvements` — short bullets, one per Improvement. Skip if none.
7. `## Fixes` — short bullets, one per Fix. Skip if none.

RULES:
- INCLUDE EVERY change you are given — do not drop any.
- Do NOT add anything not in the provided summaries. No invented facts.
- Keep concrete specifics (numbers, limits, percentages).
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
_INCLUDE_KINDS = ("feature", "improvement", "fix")
_KIND_HEADINGS = {"feature": "Features", "improvement": "Improvements", "fix": "Fixes"}


@dataclass
class Classified:
    """One PR after triage: its bucket + a clean customer-facing summary."""

    number: str
    kind: str          # feature | improvement | fix | omit
    summary: str


def _classify_user(items: list[IngestedItem]) -> str:
    lines = ["Pull requests to classify:\n"]
    for it in items:
        labels = f" [labels: {', '.join(it.labels)}]" if it.labels else ""
        lines.append(f"- #{it.external_id}: {it.title}{labels}")
        if it.body:
            body = it.body.strip()
            if len(body) > _MAX_BODY_CHARS:
                body = body[:_MAX_BODY_CHARS] + "…"
            for line in body.splitlines():
                lines.append(f"    {line}")
    return "\n".join(lines)


def _parse_classifications(
    raw: str, items: list[IngestedItem]
) -> list[Classified]:
    """Parse the triage JSON, defensively. Unknown/missing PRs FAIL OPEN to
    inclusion (as an improvement) — dropping a real change is worse than a stray
    one, which the writer can still catch."""
    text = raw.strip()
    start, end = text.find("["), text.rfind("]")
    parsed: list[dict] = []
    if start != -1 and end != -1:
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            parsed = []
    by_num = {str(d.get("number")): d for d in parsed if isinstance(d, dict)}

    out: list[Classified] = []
    for it in items:
        d = by_num.get(str(it.external_id))
        if not d:
            out.append(Classified(it.external_id, "improvement", it.title))
            continue
        kind = str(d.get("kind", "")).lower().strip()
        if kind not in (*_INCLUDE_KINDS, "omit"):
            kind = "improvement"
        summary = str(d.get("summary") or "").strip() or it.title
        out.append(Classified(it.external_id, kind, summary))
    return out


async def classify_prs(
    provider: AiProvider, api_key: str, items: list[IngestedItem]
) -> list[Classified]:
    """Step 1: triage each PR by real user impact and distil a clean summary."""
    import litellm  # lazy: heavy import stays out of the API cold-start path

    response = await litellm.acompletion(
        model=_DEFAULT_MODEL[provider],
        api_key=api_key,
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": _classify_user(items)},
        ],
        temperature=0,  # deterministic triage
    )
    raw = response.choices[0].message.content or ""
    return _parse_classifications(raw, items)


def _draft_user(
    included: list[Classified],
    profile: ProductProfile | None,
    examples: list[ReleaseExample] | None,
) -> str:
    parts: list[str] = []

    if profile:
        parts.append(
            "PRODUCT CONTEXT (use this to shape voice and framing):\n"
            + profile.as_block()
        )

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

    changes = ["CHANGES TO INCLUDE (already triaged — include EVERY item):"]
    for kind in _INCLUDE_KINDS:
        summaries = [c.summary for c in included if c.kind == kind]
        if summaries:
            changes.append(
                f"{_KIND_HEADINGS[kind]}:\n"
                + "\n".join(f"- {s}" for s in summaries)
            )
    parts.append("\n\n".join(changes))

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
    """The pipeline: triage (await) → filter omits (code) → stream the note.

    Raises ValueError if nothing user-facing survives triage, so the caller can
    show a clean "no changes to announce" message.
    """
    classified = await classify_prs(provider, api_key, items)
    included = [c for c in classified if c.kind in _INCLUDE_KINDS]
    if not included:
        raise ValueError("No user-facing changes to announce since the last release.")

    import litellm  # lazy: heavy import stays out of the API cold-start path

    response = await litellm.acompletion(
        model=_DEFAULT_MODEL[provider],
        api_key=api_key,
        messages=[
            {"role": "system", "content": _DRAFT_SYSTEM},
            {"role": "user", "content": _draft_user(included, profile, examples)},
        ],
        stream=True,
        temperature=0.4,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
