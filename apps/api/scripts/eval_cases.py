"""Golden dataset for release-note evals + demo seeding (single source of truth).

Each case carries the PR content AND the ground truth: whether a good note should
surface it, and the keywords that prove coverage (for features/fixes) or a leak
(for chores). Both the eval runner and the demo seeder read from here so they can
never drift apart.
"""

from __future__ import annotations

from app.services.draft_eval import EvalCase

REPO = "acme/analytics"

CASES: list[EvalCase] = [
    EvalCase(
        201, "Add scheduled report exports to email", ["feature"],
        "Users can now schedule any saved report to be emailed as a PDF on a daily, "
        "weekly, or monthly cadence. Set it up from the report's ••• menu → Schedule. "
        "Closes #180 — the most-requested item on our roadmap this quarter.",
        kind="feature", keywords=["schedul", "report", "email", "pdf"],
    ),
    EvalCase(
        205, "Add Slack integration for alerts", ["feature", "integrations"],
        "New Slack integration: connect a workspace under Settings → Integrations and "
        "route metric alerts (thresholds, anomalies) straight into a channel. Uses "
        "Slack's OAuth flow; tokens are stored encrypted.",
        kind="feature", keywords=["slack"],
    ),
    EvalCase(
        212, "Introduce dark mode across the dashboard", ["feature", "ui"],
        "Full dark theme for the entire app. Respects the OS preference by default and "
        "can be toggled from the profile menu. Charts, tables, and modals all themed.",
        kind="feature", keywords=["dark mode", "dark theme"],
    ),
    EvalCase(
        208, "Speed up dashboard initial load by ~60%", ["performance"],
        "Reworked the initial data fetch to run queries in parallel and stream the "
        "first widgets before the whole page is ready. p95 load dropped from 4.1s to "
        "1.6s on large workspaces.",
        kind="improvement", keywords=["load", "faster", "speed", "performance", "1.6"],
    ),
    EvalCase(
        214, "Redesign the filters panel for easier segmenting", ["improvement", "ui"],
        "The filters panel is now a single searchable surface with grouped fields and "
        "saved filter sets, instead of the old nested dropdowns. Based on 20+ user "
        "interviews where people struggled to find fields.",
        kind="improvement", keywords=["filter", "segment"],
    ),
    EvalCase(
        219, "Raise CSV export row limit from 10k to 1M", ["improvement"],
        "Exports now stream server-side, so large datasets no longer time out. The row "
        "cap is raised from 10,000 to 1,000,000.",
        kind="improvement", keywords=["csv", "row", "1,000,000", "1m", "million", "export"],
    ),
    EvalCase(
        210, "Fix incorrect revenue totals in the monthly summary", ["bug"],
        "The monthly summary double-counted refunded orders, inflating revenue. Fixed "
        "the aggregation to net out refunds. Numbers now match the billing system.",
        kind="fix", keywords=["revenue", "refund", "monthly", "total"],
    ),
    EvalCase(
        216, "Fix crash when a chart has no data points", ["bug"],
        "A chart with an empty result set threw and blanked the whole dashboard. It now "
        "renders an empty state instead. Reported by several users on new workspaces.",
        kind="fix", keywords=["chart", "crash", "empty"],
    ),
    EvalCase(
        221, "Fix timezone offset in scheduled exports", ["bug"],
        "Scheduled exports used server time instead of the workspace timezone, so daily "
        "reports arrived with the wrong day's data for non-UTC teams. Now uses the "
        "workspace's configured timezone.",
        kind="fix", keywords=["timezone", "time zone"],
    ),
    # ── The noise: a good note must NOT surface any of these ────────────────
    EvalCase(
        203, "Bump next from 15.1.0 to 15.5.2", ["dependencies"],
        "Routine dependency bump. No user-facing change.",
        kind="omit", avoid=["dependency", "bump", "15.5", "15.1"],
    ),
    EvalCase(
        207, "Refactor auth middleware into a single module", ["chore", "refactor"],
        "Internal cleanup: consolidated the scattered auth checks into one middleware. "
        "No behavior change.",
        kind="omit", avoid=["refactor", "middleware"],
    ),
    EvalCase(
        218, "Add integration tests for the export pipeline", ["test"],
        "Adds coverage for the new streaming export path. Test-only.",
        kind="omit", avoid=["integration test", "test coverage", "test-only", "unit test"],
    ),
    EvalCase(
        222, "Update CI to run on Node 20", ["ci"],
        "Bumps the CI runner to Node 20 and drops the Node 18 matrix entry.",
        kind="omit", avoid=["ci ", "node 20", "node 18", "runner"],
    ),
    EvalCase(
        224, "Tidy up README and CONTRIBUTING docs", ["docs"],
        "Docs pass: fixed broken links and clarified local setup steps.",
        kind="omit", avoid=["readme", "contributing", "broken link"],
    ),
    # ── Adversarial cases: designed to trip a title-only reader ─────────────
    # Trap 1: chore-sounding TITLE, but the body ships a real user feature.
    # A model that reads only the title will wrongly omit it.
    EvalCase(
        230, "Refactor billing module for extensibility", ["refactor"],
        "While reorganizing billing internals, this also ships annual subscription "
        "plans: customers can now switch to yearly billing and save 20%, selectable "
        "at checkout. The refactor was the groundwork; the annual plan is the payoff.",
        kind="feature", keywords=["annual", "yearly", "20%"],
    ),
    # Trap 2: feature-sounding TITLE ("Add ..."), but it's dev-tooling only.
    # A model that includes everything titled "Add" will wrongly surface it.
    EvalCase(
        231, "Add ESLint rule for exhaustive hook deps", ["chore"],
        "Adds a lint rule that flags missing React hook dependencies at build time. "
        "Developer tooling only — no runtime or user-facing change.",
        kind="omit", avoid=["eslint", "lint rule", "exhaustive", "hook dep"],
    ),
    # Trap 3: a real feature with an EMPTY body — only the title to go on.
    # Tests robustness when there's no description to lean on.
    EvalCase(
        232, "Add bulk delete for saved views", ["feature"],
        "",
        kind="feature", keywords=["bulk delete", "bulk", "saved view"],
    ),
    # Trap 4: a squash-merge bundling a feature AND an internal dep bump.
    # The note must surface the feature but NOT mention the dependency.
    EvalCase(
        233, "Weekly batch: shortcuts + housekeeping", [],
        "This batch includes:\n"
        "- Keyboard shortcuts for dashboard navigation (press ? to see them)\n"
        "- Bumped the internal charting library from 4.2 to 4.3\n"
        "- Minor logging cleanup",
        kind="feature",
        keywords=["keyboard shortcut", "shortcut"],
        avoid=["charting library", "4.3", "logging"],
    ),
]
