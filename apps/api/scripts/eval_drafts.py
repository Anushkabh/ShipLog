"""Run the drafting pipeline against the golden dataset and score it.

Uses a project's stored BYOK key + product profile, runs the SAME `stream_draft`
the product uses, and grades each output on structure / coverage / noise. Run it
after any prompt change to catch regressions before they ship.

Run:
  PYTHONPATH=. .venv/bin/python scripts/eval_drafts.py            # 1 run
  PYTHONPATH=. .venv/bin/python scripts/eval_drafts.py --runs 3   # consistency
  PYTHONPATH=. .venv/bin/python scripts/eval_drafts.py --slug my-project
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from eval_cases import CASES
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AiCredential, IngestedItem, Project
from app.services import crypto
from app.services.ai import ProductProfile, stream_draft
from app.services.draft_eval import Scorecard, score_draft

logging.disable(logging.INFO)  # keep SQL noise out of the scorecard


async def _draft(provider, key, items, profile) -> str:
    chunks = [c async for c in stream_draft(provider, key, items, profile=profile)]
    return "".join(chunks)


def _render(card: Scorecard, label: str) -> None:
    verdict = "PASS ✅" if card.passed else "FAIL ❌"
    print(f"\n── {label} ──  overall {card.overall:.2f}   {verdict}")
    cov = f"{len(card.covered)}/{card.total_to_cover}"
    print(f"  coverage : {cov} user-facing changes included"
          + (f"   ⚠ MISSING: {card.missing}" if card.missing else "   ✓"))
    clean = card.total_to_omit - len(card.leaked)
    print(f"  noise    : {clean}/{card.total_to_omit} chore PRs kept out"
          + (f"   ⚠ LEAKED: {card.leaked}" if card.leaked else "   ✓"))
    if card.total_impurity_checks:
        pure = card.total_impurity_checks - len(card.impurities)
        print(f"  purity   : {pure}/{card.total_impurity_checks} bundled PRs shed their chore"
              + (f"   ⚠ IMPURE: {card.impurities}" if card.impurities else "   ✓"))
    checks = "  ".join(f"{k} {'✓' if v else '✗'}" for k, v in card.structure_checks.items())
    print(f"  structure: {checks}")


async def main(slug: str, runs: int) -> None:
    async with SessionLocal() as db:
        project = await db.scalar(select(Project).where(Project.slug == slug))
        if not project:
            raise SystemExit(f"No project with slug '{slug}'.")
        cred = await db.scalar(
            select(AiCredential).where(AiCredential.project_id == project.id)
        )
        if not cred:
            raise SystemExit(f"Project '{slug}' has no AI key configured.")
        key = crypto.decrypt(cred.encrypted_key)
        profile = ProductProfile(
            name=project.name,
            summary=project.product_summary,
            audience=project.audience,
            tone=project.tone,
        )

    # In-memory PRs (no DB needed) so the eval set is self-contained.
    items = [
        IngestedItem(
            external_id=str(c.number), title=c.title, body=c.body, labels=c.labels
        )
        for c in CASES
    ]

    print(f"Evaluating '{project.name}' via {cred.provider.value} · {runs} run(s) · "
          f"{len(CASES)} PRs ({sum(c.should_appear for c in CASES)} to include, "
          f"{sum(not c.should_appear for c in CASES)} to omit)")

    cards: list[Scorecard] = []
    for i in range(runs):
        try:
            markdown = await _draft(cred.provider, key, items, profile)
        except Exception as e:
            print(f"  run {i + 1}: provider error — {str(e)[:160]}")
            continue
        card = score_draft(CASES, markdown)
        cards.append(card)
        _render(card, f"run {i + 1}")

    if len(cards) > 1:
        avg = sum(c.overall for c in cards) / len(cards)
        passes = sum(c.passed for c in cards)
        avg_cov = sum(c.coverage_rate for c in cards) / len(cards)
        avg_noise = sum(c.noise_clean_rate for c in cards) / len(cards)
        print(f"\n══ AGGREGATE ({len(cards)} runs) ══")
        print(f"  avg overall : {avg:.2f}")
        print(f"  pass rate   : {passes}/{len(cards)}")
        print(f"  avg coverage: {avg_cov:.0%}   avg noise-clean: {avg_noise:.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="smart-release-demo")
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    asyncio.run(main(args.slug, args.runs))
