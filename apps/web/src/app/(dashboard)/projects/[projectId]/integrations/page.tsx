"use client";

import * as React from "react";
import { useParams, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { CircleAlert, CircleCheck, Github, Loader2, Plug, RefreshCw, Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Integration, Project } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConnectGithubButton } from "@/components/integrations/connect-github-button";

const GH_ERRORS: Record<string, string> = {
  state: "That connection link expired or didn't match. Try connecting again.",
  auth: "Your session expired mid-connect. Sign in and try again.",
  forbidden: "You need admin access on this project to connect a repo.",
  project: "Couldn't find the project to connect to.",
  installation: "GitHub didn't return a valid installation. Try again.",
  github: "Couldn't reach GitHub to list your repos. Try again in a moment.",
};

export default function IntegrationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const { mutate } = useSWRConfig();

  const connected = searchParams.get("connected");
  const ghError = searchParams.get("gh_error");

  // A fresh return from the GitHub install flow may have added repos server-side
  // before this page mounts — revalidate so they show without a manual refresh.
  React.useEffect(() => {
    if (connected !== null) {
      mutate(`/api/projects/${projectId}/integrations`);
    }
  }, [connected, projectId, mutate]);

  const { data: project } = useSWR<Project>(
    `/api/projects/${projectId}`,
    () => api.project(projectId),
  );
  const { data: integrations, isLoading } = useSWR<Integration[]>(
    `/api/projects/${projectId}/integrations`,
    () => api.integrations(projectId),
  );

  const [removing, setRemoving] = React.useState<string | null>(null);
  const [syncing, setSyncing] = React.useState<string | null>(null);
  const [syncMsg, setSyncMsg] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function sync(id: string, repo: string) {
    setSyncing(id);
    setSyncMsg(null);
    setError(null);
    try {
      const { ingested } = await api.syncIntegration(projectId, id);
      setSyncMsg(
        `Synced ${repo}: ${ingested} merged ${ingested === 1 ? "PR" : "PRs"} pulled.`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : `Couldn't sync ${repo}.`,
      );
    } finally {
      setSyncing(null);
    }
  }

  async function disconnect(id: string, repo: string) {
    if (!confirm(`Disconnect ${repo}? New PRs will stop being ingested.`)) {
      return;
    }
    setRemoving(id);
    setError(null);
    try {
      await api.deleteIntegration(projectId, id);
      await mutate(`/api/projects/${projectId}/integrations`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't disconnect.");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <>
      <Topbar
        crumbs={[
          {
            label: project?.name ?? "Project",
            href: `/projects/${projectId}/releases`,
          },
          { label: "Integrations" },
        ]}
      />
      <div className="flex flex-col gap-5 p-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Integrations</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Connect GitHub repos so merged PRs flow in as material for AI
              release drafts.
            </p>
          </div>
          <ConnectGithubButton projectId={projectId} />
        </div>

        {connected !== null && (
          <div className="flex items-center gap-2 rounded-md border border-emerald-600/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
            <CircleCheck className="size-4 flex-none" />
            {Number(connected) > 0
              ? `Connected ${connected} ${Number(connected) === 1 ? "repo" : "repos"} from GitHub.`
              : "GitHub connected, but no repositories were granted. Re-run and pick at least one repo."}
          </div>
        )}
        {ghError && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <CircleAlert className="size-4 flex-none" />
            {GH_ERRORS[ghError] ?? "Something went wrong connecting GitHub. Try again."}
          </div>
        )}
        {syncMsg && (
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-foreground">
            <RefreshCw className="size-4 flex-none" />
            {syncMsg}
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {isLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : integrations && integrations.length > 0 ? (
          <Card className="divide-y divide-border p-0">
            {integrations.map((it) => (
              <div key={it.id} className="flex items-center gap-3 p-4">
                <span className="grid size-9 flex-none place-items-center rounded-md bg-muted text-foreground">
                  <Github className="size-4.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-sm font-semibold">
                    {it.repo_full_name}
                  </div>
                  <div className="text-xs text-subtle">
                    GitHub · installation{" "}
                    <span className="font-mono">{it.installation_id}</span>
                  </div>
                </div>
                <Button
                  variant="subtle"
                  size="sm"
                  onClick={() => sync(it.id, it.repo_full_name)}
                  disabled={syncing === it.id}
                >
                  {syncing === it.id ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <RefreshCw />
                  )}
                  Sync
                </Button>
                <Button
                  variant="subtle"
                  size="icon"
                  onClick={() => disconnect(it.id, it.repo_full_name)}
                  disabled={removing === it.id}
                  aria-label={`Disconnect ${it.repo_full_name}`}
                >
                  {removing === it.id ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <Trash2 />
                  )}
                </Button>
              </div>
            ))}
          </Card>
        ) : (
          <Card className="flex flex-col items-center gap-3 border-dashed py-14 text-center">
            <span className="grid size-11 place-items-center rounded-xl bg-muted text-muted-foreground">
              <Plug className="size-5" />
            </span>
            <div>
              <p className="font-semibold">No repos connected</p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Connect GitHub to start ingesting merged pull requests.
              </p>
            </div>
            <ConnectGithubButton projectId={projectId} />
          </Card>
        )}
      </div>
    </>
  );
}
