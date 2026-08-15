import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Code2,
  GitPullRequest,
  Github,
  Globe,
  Mail,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Shiplog — Release notes your users actually read",
  description:
    "Open-source, self-hostable changelog platform. Connect a GitHub repo, let AI draft release notes from merged PRs, and publish to a hosted changelog, embeddable widget, and email subscribers.",
};

const FEATURES = [
  {
    icon: Sparkles,
    title: "AI drafts from your PRs",
    body: "Bring your own provider key. Shiplog turns merged pull requests into a clean draft you review before publishing — never auto-posted.",
  },
  {
    icon: Globe,
    title: "Hosted changelog",
    body: "Every project gets a fast, SEO-ready public changelog with permalinks — on a subdomain or your own verified custom domain.",
  },
  {
    icon: Code2,
    title: "Embeddable widget",
    body: "Drop in widget.js to show a “What’s new” feed inside your product. Redis-cached, so a million readers cost effectively nothing.",
  },
  {
    icon: Mail,
    title: "Email subscribers",
    body: "Double opt-in subscribers and one-click broadcasts on publish, with HMAC-signed unsubscribe links. No third-party newsletter tool.",
  },
  {
    icon: ShieldCheck,
    title: "Self-hostable & yours",
    body: "Runs on always-free tiers at effectively zero cost. Your keys are AES-256-GCM encrypted at rest. Open source, no lock-in.",
  },
  {
    icon: Github,
    title: "GitHub-native",
    body: "Sign in with GitHub, connect repos via a GitHub App, and let signed webhooks stream merged PRs straight into your release pipeline.",
  },
];

const STEPS = [
  {
    icon: GitPullRequest,
    title: "Connect a repo",
    body: "Install the GitHub App and connect a repository. Merged PRs flow in as ingested items, deduped and idempotent.",
  },
  {
    icon: Sparkles,
    title: "Draft with AI",
    body: "Open a release and draft from the PRs merged since your last one. Edit the markdown with a live preview alongside.",
  },
  {
    icon: Send,
    title: "Publish everywhere",
    body: "One publish pushes to your changelog site, the embedded widget, and your email subscribers — all at once.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-5">
          <Link href="/" className="flex items-center gap-2.5 font-semibold">
            <span className="grid size-[22px] place-items-center rounded-md bg-gradient-to-br from-primary to-violet-500 text-[13px] font-bold text-primary-foreground shadow-sm">
              S
            </span>
            <span className="text-[15px] tracking-tight">Shiplog</span>
          </Link>
          <nav className="ml-6 hidden items-center gap-5 text-sm text-muted-foreground sm:flex">
            <a href="#features" className="transition-colors hover:text-foreground">
              Features
            </a>
            <a href="#how" className="transition-colors hover:text-foreground">
              How it works
            </a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Button asChild size="sm">
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto grid max-w-5xl gap-12 px-5 py-16 md:grid-cols-2 md:items-center md:py-24">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="size-3 text-primary-text" />
              Open-source · self-hostable
            </span>
            <h1 className="mt-5 text-balance text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl">
              Release notes your users actually read.
            </h1>
            <p className="mt-4 max-w-md text-pretty text-lg text-muted-foreground">
              Connect a GitHub repo, let AI draft your changelog from merged
              PRs, and publish to a hosted site, an embeddable widget, and email
              subscribers — from one place.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link href="/login">
                  Get started
                  <ArrowRight />
                </Link>
              </Button>
              <Button asChild size="lg" variant="ghost">
                <a href="#how">See how it works</a>
              </Button>
            </div>
            <p className="mt-4 text-xs text-subtle">
              No credit card. Runs on always-free tiers.
            </p>
          </div>

          {/* Self-contained product preview */}
          <ChangelogPreview />
        </section>

        {/* Features */}
        <section
          id="features"
          className="scroll-mt-16 border-t border-border bg-muted/30"
        >
          <div className="mx-auto max-w-5xl px-5 py-16 md:py-20">
            <div className="max-w-xl">
              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
                Everything a changelog needs
              </h2>
              <p className="mt-2 text-muted-foreground">
                One tool for the whole loop — from merged PR to the reader&rsquo;s
                inbox.
              </p>
            </div>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <div
                  key={f.title}
                  className="rounded-xl border border-border bg-card p-5 shadow-sm"
                >
                  <span className="grid size-9 place-items-center rounded-lg bg-primary-weak text-primary-text">
                    <f.icon className="size-[18px]" />
                  </span>
                  <h3 className="mt-3.5 font-semibold tracking-tight">
                    {f.title}
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {f.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="scroll-mt-16">
          <div className="mx-auto max-w-5xl px-5 py-16 md:py-20">
            <div className="max-w-xl">
              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
                From merged PR to published, in three steps
              </h2>
            </div>
            <ol className="mt-10 grid gap-6 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative">
                  <div className="flex items-center gap-3">
                    <span className="tabnum grid size-8 flex-none place-items-center rounded-lg border border-border bg-card text-sm font-semibold text-primary-text">
                      {i + 1}
                    </span>
                    <s.icon className="size-4 text-muted-foreground" />
                  </div>
                  <h3 className="mt-4 font-semibold tracking-tight">
                    {s.title}
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {s.body}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="border-t border-border bg-muted/30">
          <div className="mx-auto flex max-w-5xl flex-col items-center gap-5 px-5 py-16 text-center md:py-20">
            <h2 className="text-balance text-2xl font-bold tracking-tight sm:text-3xl">
              Start shipping a changelog today.
            </h2>
            <p className="max-w-md text-muted-foreground">
              Spin it up locally in minutes, or self-host it for good. Your
              repos, your keys, your data.
            </p>
            <Button asChild size="lg">
              <Link href="/login">
                Get started
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-3 px-5 py-6 text-sm text-subtle sm:flex-row">
          <div className="flex items-center gap-2">
            <span className="grid size-5 place-items-center rounded bg-gradient-to-br from-primary to-violet-500 text-[10px] font-bold text-primary-foreground">
              S
            </span>
            <span>Shiplog — open-source changelog platform</span>
          </div>
          <span>FastAPI · Next.js · Postgres · self-hostable</span>
        </div>
      </footer>
    </div>
  );
}

/** A static, data-free product preview for the hero — mirrors the real
 * changelog aesthetic without a live fetch. */
function ChangelogPreview() {
  const entries = [
    {
      date: "Jul 10",
      title: "Scheduled digests & SAML SSO",
      version: "v2.4.0",
      tone: "published",
      tags: ["Feature", "Enterprise"],
    },
    {
      date: "Jul 3",
      title: "Widget dark mode & theming API",
      version: "v2.3.1",
      tone: "published",
      tags: ["Widget"],
    },
    {
      date: "—",
      title: "Batched PR ingestion",
      version: "draft",
      tone: "draft",
      tags: ["Performance"],
    },
  ] as const;

  return (
    <div className="rounded-xl border border-border bg-card p-2 shadow-lg">
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <span className="size-2.5 rounded-full bg-status-draft/40" />
        <span className="size-2.5 rounded-full bg-status-scheduled/50" />
        <span className="size-2.5 rounded-full bg-status-published/50" />
        <span className="ml-2 font-mono text-[11px] text-subtle">
          acme.shiplog.app
        </span>
      </div>
      <div className="rounded-lg border border-border bg-background p-4">
        <div className="mb-3 text-[13px] font-bold tracking-tight">
          What&rsquo;s new
        </div>
        <div className="flex flex-col divide-y divide-border">
          {entries.map((e) => (
            <div key={e.title} className="flex items-start gap-3 py-3 first:pt-0">
              <span className="tabnum mt-0.5 w-10 flex-none text-[11px] font-medium text-subtle">
                {e.date}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-semibold">
                    {e.title}
                  </span>
                  <span
                    className={
                      "size-1.5 flex-none rounded-full " +
                      (e.tone === "published"
                        ? "bg-status-published"
                        : "bg-status-draft")
                    }
                  />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[10.5px] text-subtle">
                    {e.version}
                  </span>
                  {e.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
