"""Offline evaluation of AI-drafted release notes (the "is it actually good?" layer).

A single prompt is easy to eyeball once and impossible to trust over time — every
tweak risks silently regressing. This module scores a generated note against a
GOLDEN dataset of PRs whose ground truth we know, on three axes that map to the
product's promises:

  • structure — did it produce the house format (title, sections)?
  • coverage  — did every user-facing change make it in?  (misses = bad)
  • noise     — did every chore/refactor/dep/test/doc stay OUT? (leaks = bad)

Scoring is deterministic keyword matching (no model in the loop) so evals are
fast, free, and repeatable. It's intentionally simple; an LLM-judge pass can be
layered on later for paraphrase-robust grading.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """One PR plus the ground truth of how a good note should treat it."""

    number: int
    title: str
    labels: list[str]
    body: str
    # "feature" | "improvement" | "fix" want inclusion; "omit" wants exclusion.
    kind: str
    # For inclusion kinds: at least one keyword must appear in the note.
    keywords: list[str] = field(default_factory=list)
    # For "omit": none of these distinctive terms may appear.
    avoid: list[str] = field(default_factory=list)

    @property
    def should_appear(self) -> bool:
        return self.kind != "omit"


@dataclass
class Scorecard:
    structure_checks: dict[str, bool]
    covered: list[str]
    missing: list[str]      # user-facing changes the note dropped (bad)
    leaked: list[str]       # whole chore PRs that leaked in (bad)
    impurities: list[str]   # a kept PR that dragged its embedded chore in (bad)
    total_to_cover: int
    total_to_omit: int
    total_impurity_checks: int

    @property
    def coverage_rate(self) -> float:
        return len(self.covered) / self.total_to_cover if self.total_to_cover else 1.0

    @property
    def noise_clean_rate(self) -> float:
        total = self.total_to_omit + self.total_impurity_checks
        if not total:
            return 1.0
        return (total - len(self.leaked) - len(self.impurities)) / total

    @property
    def structure_rate(self) -> float:
        checks = self.structure_checks
        return sum(checks.values()) / len(checks) if checks else 1.0

    @property
    def overall(self) -> float:
        """Weighted headline score. Coverage and noise dominate; structure is a
        smaller slice because a well-formatted note that drops features is still
        a failure."""
        return round(
            0.45 * self.coverage_rate
            + 0.40 * self.noise_clean_rate
            + 0.15 * self.structure_rate,
            3,
        )

    @property
    def passed(self) -> bool:
        # The bar we'd actually ship against: nothing dropped, nothing leaked.
        return (
            not self.missing
            and not self.leaked
            and not self.impurities
            and self.structure_rate >= 0.75
        )


def score_draft(cases: list[EvalCase], markdown: str) -> Scorecard:
    text = markdown.lower()

    structure_checks = {
        "has_title": "title:" in text.splitlines()[0].lower()
        if text.strip()
        else False,
        "has_whats_new": "what's new" in text or "whats new" in text,
        "has_sections": markdown.count("## ") >= 2,
        "has_intro": _has_intro_paragraph(markdown),
    }

    covered: list[str] = []
    missing: list[str] = []
    leaked: list[str] = []
    impurities: list[str] = []
    total_to_cover = 0
    total_to_omit = 0
    total_impurity_checks = 0

    for c in cases:
        if c.should_appear:
            total_to_cover += 1
            terms = c.keywords or [c.title]
            if any(t.lower() in text for t in terms):
                covered.append(c.title)
            else:
                missing.append(c.title)
            # A kept PR may still carry an embedded chore that must NOT surface.
            if c.avoid:
                total_impurity_checks += 1
                if any(t.lower() in text for t in c.avoid):
                    impurities.append(c.title)
        else:
            total_to_omit += 1
            terms = c.avoid or c.keywords or [c.title]
            if any(t.lower() in text for t in terms):
                leaked.append(c.title)

    return Scorecard(
        structure_checks=structure_checks,
        covered=covered,
        missing=missing,
        leaked=leaked,
        impurities=impurities,
        total_to_cover=total_to_cover,
        total_to_omit=total_to_omit,
        total_impurity_checks=total_impurity_checks,
    )


def _has_intro_paragraph(markdown: str) -> bool:
    """True if there's prose before the first heading (the warm intro)."""
    for line in markdown.splitlines():
        s = line.strip()
        if not s or s.upper().startswith(("TITLE:", "VERSION:")):
            continue
        return not s.startswith("#")  # first real line is prose, not a heading
    return False
