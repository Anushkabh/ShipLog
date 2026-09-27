"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  ArrowRight,
  Check,
  CircleAlert,
  CircleCheck,
  Copy,
  ExternalLink,
  FlaskConical,
  Loader2,
  MonitorSmartphone,
  Sparkles,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Project, SetupStatus } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConnectGithubButton } from "@/components/integrations/connect-github-button";
import { useSession } from "@/components/auth/session";
import { useOrigin } from "@/lib/use-origin";

const GH_ERRORS: Record<string, string> = {
  state: "That connection link expired or didn't match. Try connecting again.",
  auth: "Your session expired mid-connect. Sign in and try again.",
  forbidden: "You need admin access on this project to connect a repo.",
  project: "Couldn't find the project to connect to.",
  installation: "GitHub didn't return a valid installation. Try again.",
  github: "Couldn't reach GitHub to list your repos. Try again in a moment.",
};

export default function SetupPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const { user } = useSession();
  const isDemo = !!user?.is_demo;
  const connected = searchParams.get("connected");
  const ghError = searchParams.get("gh_error");

  const { data: project } = useSWR<Project>(`/api/projects/${projectId}`, () =>
    api.project(projectId),
  );
  const {
    data: s,
    isLoading,
    mutate,
  } = useSWR<SetupStatus>(`/api/projects/${projectId}/setup`, () => api.setupStatus(projectId), {
    // Keep polling while the post-connect job is still pulling PRs / reading docs.
    refreshInterval: (d) =>
      d && d.repos_connected > 0 && d.published === 0 && (d.prs_pending === 0 || !d.profile_set)
        ? 3000
        : 0,
  });

  const [loadingSample, setLoadingSample] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function trySample() {
    setLoadingSample(true);
    setError(null);
    try {
      await api.loadSampleData(projectId);
      await mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load sample data.");
    } finally {
      setLoadingSample(false);
    }
  }

  const origin = useOrigin();
  // Steps track "the changes since your last release": a project with history
  // (e.g. imported past releases) still has steps 2–3 open while PRs wait.
  const caughtUp = !!s && s.prs_pending === 0 && s.published > 0;
  const step1Done = !!s && (s.prs_pending > 0 || s.published > 0 || s.drafts > 0);
  const step2Done = !!s && (s.drafts > 0 || caughtUp);
  const step3Done = caughtUp && !!s && s.drafts === 0;
  const syncing = !!s && s.repos_connected > 0 && s.prs_pending === 0 && s.published === 0;
  const publicUrl = s ? `${origin}/c/${s.public_key}` : "";
  const demoAppUrl = s ? `/demo/app?key=${s.public_key}` : "";
  const snippet = s
    ? `<script src="${origin}/widget.js" data-key="${s.public_key}" async></script>`
    : "";

  return (
    <>
      <Topbar
        crumbs={[
          { label: project?.name ?? "Project", href: `/projects/${projectId}/releases` },
          { label: "Get started" },
        ]}
      />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-6 md:p-10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Get started{project ? ` with ${project.name}` : ""}
          </h1>
          <p className="mt-1 text-muted-foreground">
            Three steps from merged pull requests to a published, AI-written release note.
          </p>
        </div>

        {isDemo && (
          <Card className="border-primary/30 bg-primary-weak/40 p-5">
            <h2 className="flex items-center gap-2 font-semibold">
              <Sparkles className="size-4 text-primary-text" /> Welcome to the Shiplog demo
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              <strong className="text-foreground">Acme Analytics</strong> is a fictional SaaS
              product. Since its last release, the team merged{" "}
              <strong className="text-foreground">18 pull requests</strong> — new features and
              fixes, plus internal chores (dependency bumps, refactors, CI tweaks) that customers
              should never see. Shiplog already pulled them in and learned the product&rsquo;s
              voice from its past releases.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              <strong className="text-foreground">Your turn:</strong> click{" "}
              <em>Draft my release</em> and watch the AI write the customer-facing note, then
              publish it and open the customer app to see it pop up in the widget.
            </p>
            <p className="mt-2 text-xs text-subtle">
              Things to notice: the chores are left out, and a PR titled &ldquo;Refactor billing
              module&rdquo; still makes it in — because its description shows it actually
              shipped annual plans.
            </p>
          </Card>
        )}

        {connected !== null && (
          <Banner tone="ok">
            {Number(connected) > 0
              ? `Connected ${connected} ${Number(connected) === 1 ? "repo" : "repos"}. Pulling your recent pull requests and reading your docs…`
              : "GitHub connected, but no repositories were granted. Connect again and pick at least one repo."}
          </Banner>
        )}
        {ghError && (
          <Banner tone="error">{GH_ERRORS[ghError] ?? "Something went wrong connecting GitHub."}</Banner>
        )}
        {error && <Banner tone="error">{error}</Banner>}

        {isLoading || !s ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : (
          <ol className="flex flex-col gap-4">
            {/* ① Bring in changes */}
            <Step
              n={1}
              done={step1Done}
              active={!step1Done}
              title="Bring in your changes"
              body="Connect GitHub and we'll pull your recently merged pull requests, import your past releases, and learn about your product from your docs — automatically."
            >
              {s.repos_connected > 0 && (
                <ul className="flex flex-col gap-1 text-sm">
                  <StatusLine ok>
                    {s.repos_connected} {s.repos_connected === 1 ? "repo" : "repos"} connected
                  </StatusLine>
                  <StatusLine ok={s.prs_pending > 0} pending={syncing}>
                    {s.prs_pending > 0
                      ? `${s.prs_pending} merged PRs ready to draft from`
                      : syncing
                        ? "Pulling your merged PRs…"
                        : "No new merged PRs since your last release"}
                  </StatusLine>
                  <StatusLine ok={s.profile_set} pending={!s.profile_set}>
                    {s.profile_set
                      ? "Product context learned from your docs"
                      : "Reading your docs to learn about your product…"}
                  </StatusLine>
                </ul>
              )}
              {!step1Done && (
                <div className="flex flex-wrap items-center gap-2">
                  <ConnectGithubButton projectId={projectId} />
                  <Button variant="accent" onClick={trySample} disabled={loadingSample}>
                    {loadingSample ? <Loader2 className="animate-spin" /> : <FlaskConical />}
                    Try with sample data
                  </Button>
                </div>
              )}
              {!step1Done && (
                <p className="text-xs text-subtle">
                  No repo handy? Sample data loads 18 realistic PRs (features, fixes, and chores
                  the AI should leave out) so you can try the whole flow.
                </p>
              )}
            </Step>

            {/* ② Draft */}
            <Step
              n={2}
              done={step2Done}
              active={step1Done && !step2Done}
              title="Draft your first release with AI"
              body="One click turns those PRs into a customer-facing note: a headline, a short intro, highlights, and grouped improvements and fixes. Chores, refactors, and dependency bumps are left out."
            >
              {step1Done && !s.ai_ready && (
                <p className="text-sm text-status-scheduled">
                  AI drafting isn&rsquo;t available right now.{" "}
                  <Link href={`/projects/${projectId}/ai`} className="font-medium underline">
                    Add your own provider key
                  </Link>{" "}
                  to continue.
                </p>
              )}
              {step1Done && s.ai_ready && s.prs_pending > 0 && s.drafts === 0 && (
                <div>
                  <Button asChild size="lg">
                    <Link href={`/projects/${projectId}/releases/new?autodraft=1`}>
                      <Sparkles />
                      Draft my release
                    </Link>
                  </Button>
                </div>
              )}
              {s.drafts > 0 && (
                <p className="text-sm text-muted-foreground">
                  You have {s.drafts} unpublished {s.drafts === 1 ? "draft" : "drafts"} — open it
                  from Releases to review and publish.
                </p>
              )}
              {step2Done && (
                <Link
                  href={`/projects/${projectId}/releases`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary-text"
                >
                  View your releases <ArrowRight className="size-3.5" />
                </Link>
              )}
            </Step>

            {/* ③ Publish & share */}
            <Step
              n={3}
              done={step3Done}
              active={step2Done && !step3Done}
              title="Publish and share"
              body="Review the draft, then publish. Your hosted changelog goes live instantly, and you can embed an in-app “What’s new” widget with one line."
            >
              {s.published > 0 ? (
                <div className="flex flex-col gap-3">
                  <CopyRow label="Public changelog" value={publicUrl} href={publicUrl} />
                  <CopyRow label="In-app widget (one line)" value={snippet} mono />
                  <div>
                    <Button asChild variant="accent">
                      <a href={demoAppUrl} target="_blank" rel="noopener">
                        <MonitorSmartphone />
                        See it inside a customer&rsquo;s app
                      </a>
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-subtle">
                  Publish from the editor — this step fills in with your public links.
                </p>
              )}
            </Step>
          </ol>
        )}

        <p className="text-center text-sm text-subtle">
          Want to tune the voice?{" "}
          <Link href={`/projects/${projectId}/ai`} className="font-medium text-primary-text underline">
            Product context &amp; AI settings
          </Link>
        </p>
      </div>
    </>
  );
}

function Step({
  n,
  done,
  active,
  title,
  body,
  children,
}: {
  n: number;
  done: boolean;
  active: boolean;
  title: string;
  body: string;
  children?: React.ReactNode;
}) {
  return (
    <li>
      <Card
        className={cn(
          "flex gap-4 p-5 transition",
          active && "border-primary/40 shadow-sm ring-1 ring-primary/15",
          !active && !done && "opacity-60",
        )}
      >
        <span
          className={cn(
            "grid size-8 flex-none place-items-center rounded-full text-sm font-bold",
            done
              ? "bg-status-published-bg text-status-published"
              : active
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-subtle",
          )}
        >
          {done ? <Check className="size-4" /> : n}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div>
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">{body}</p>
          </div>
          {children}
        </div>
      </Card>
    </li>
  );
}

function StatusLine({
  ok,
  pending,
  children,
}: {
  ok?: boolean;
  pending?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-2">
      {ok ? (
        <CircleCheck className="size-4 flex-none text-status-published" />
      ) : pending ? (
        <Loader2 className="size-4 flex-none animate-spin text-subtle" />
      ) : (
        <span className="size-4 flex-none rounded-full border border-border" />
      )}
      <span className={ok ? "text-foreground" : "text-muted-foreground"}>{children}</span>
    </li>
  );
}

function CopyRow({
  label,
  value,
  href,
  mono,
}: {
  label: string;
  value: string;
  href?: string;
  mono?: boolean;
}) {
  const [copied, setCopied] = React.useState(false);
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-subtle">{label}</div>
      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-2">
        <code className={cn("min-w-0 flex-1 truncate text-[13px]", mono && "font-mono")}>{value}</code>
        {href && (
          <Button asChild variant="subtle" size="icon" aria-label={`Open ${label}`}>
            <a href={href} target="_blank" rel="noopener">
              <ExternalLink />
            </a>
          </Button>
        )}
        <Button
          variant="subtle"
          size="icon"
          aria-label={`Copy ${label}`}
          onClick={async () => {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check /> : <Copy />}
        </Button>
      </div>
    </div>
  );
}

function Banner({ tone, children }: { tone: "ok" | "error"; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
        tone === "ok"
          ? "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
          : "border-destructive/30 bg-destructive/10 text-destructive",
      )}
    >
      {tone === "ok" ? <CircleCheck className="size-4 flex-none" /> : <CircleAlert className="size-4 flex-none" />}
      {children}
    </div>
  );
}
