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

from app.models import AiProvider, IngestedItem

# Sensible free/cheap default model per provider; the user can't pick a model in
# the MVP, we choose a good general one for each.
_DEFAULT_MODEL = {
    AiProvider.OPENAI: "gpt-4o-mini",
    AiProvider.ANTHROPIC: "claude-3-5-haiku-latest",
    AiProvider.GEMINI: "gemini/gemini-1.5-flash",
    AiProvider.GROQ: "groq/llama-3.3-70b-versatile",
}

_SYSTEM = (
    "You are a release-notes writer. Turn merged pull requests into concise, "
    "customer-facing changelog notes. Rules: describe USER IMPACT, not "
    "implementation details. Omit chores, refactors, dependency bumps, and CI "
    "changes entirely. Group items under markdown headings '### Added', "
    "'### Improved', and '### Fixed' (skip any group that's empty). Use short "
    "bullet points. No preamble, no conclusion — output only the markdown."
)


def _prompt(items: list[IngestedItem]) -> str:
    lines = ["Here are the merged pull requests since the last release:\n"]
    for it in items:
        labels = f" [labels: {', '.join(it.labels)}]" if it.labels else ""
        lines.append(f"- #{it.external_id}: {it.title}{labels}")
        if it.body:
            snippet = it.body.strip().splitlines()[0][:200]
            if snippet:
                lines.append(f"    {snippet}")
    lines.append("\nWrite the release notes now.")
    return "\n".join(lines)


async def stream_draft(
    provider: AiProvider, api_key: str, items: list[IngestedItem]
) -> AsyncIterator[str]:
    """Yield markdown chunks as the model produces them (for SSE)."""
    import litellm  # lazy: heavy import stays out of the API cold-start path

    response = await litellm.acompletion(
        model=_DEFAULT_MODEL[provider],
        api_key=api_key,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _prompt(items)},
        ],
        stream=True,
        temperature=0.4,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
