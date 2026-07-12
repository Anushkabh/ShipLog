"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Plus } from "lucide-react";

import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import type { Project, Release, ReleaseStatus } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/releases/status-badge";

const PIPELINE: { key: ReleaseStatus; label: string; dot: string }[] = [
  { key: "draft", label: "Draft", dot: "bg-status-draft" },
  { key: "scheduled", label: "Scheduled", dot: "bg-status-scheduled" },
  { key: "published", label: "Published", dot: "bg-status-published" },
];

export default function ReleasesPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: project } = useSWR<Project>(
    `/api/projects/${projectId}`,
    () => api.project(projectId),
  );
  const { data: releases, isLoading } = useSWR<Release[]>(
    `/api/projects/${projectId}/releases`,
    () => api.releases(projectId),
  );

  const counts = (releases ?? []).reduce(
    (acc, r) => {
      acc[r.status] = (acc[r.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<ReleaseStatus, number>,
  );

  const newHref = `/projects/${projectId}/releases/new`;

  return (
    <>
      <Topbar
        crumbs={[{ label: project?.name ?? "Project", muted: false }]}
      />
      <div className="flex flex-col gap-5 p-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Releases</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Draft, schedule, and publish changelog entries for your public
              site and widget.
            </p>
          </div>
          <Button asChild>
            <Link href={newHref}>
              <Plus />
              New release
            </Link>
          </Button>
        </div>

        {/* Status pipeline */}
        <div className="grid grid-cols-3 gap-3">
          {PIPELINE.map((s) => (
            <Card key={s.key} className="flex flex-col gap-1.5 p-4">
              <span className="flex items-center gap-2 text-[12.5px] font-medium text-muted-foreground">
                <span className={cn("size-1.5 rounded-full", s.dot)} />
                {s.label}
              </span>
              <span className="tabnum text-2xl font-bold tracking-tight">
                {isLoading ? "—" : (counts[s.key] ?? 0)}
              </span>
            </Card>
          ))}
        </div>

        {/* Table */}
        <Card className="overflow-hidden p-0">
          {isLoading ? (
            <div className="flex flex-col gap-3 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : releases && releases.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/60">
                    <Th>Release</Th>
                    <Th>Version</Th>
                    <Th>Status</Th>
                    <Th>Tags</Th>
                    <Th>Published</Th>
                  </tr>
                </thead>
                <tbody>
                  {releases.map((r) => (
                    <tr
                      key={r.id}
                      className="group border-b border-border last:border-0 hover:bg-muted/50"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/projects/${projectId}/releases/${r.id}`}
                          className="flex items-center gap-2.5"
                        >
                          <span className="font-semibold group-hover:text-primary-text">
                            {r.title}
                          </span>
                          {r.ai_generated && (
                            <span className="rounded bg-primary-weak px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary-text">
                              AI
                            </span>
                          )}
                          {r.is_private && (
                            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-subtle">
                              Private
                            </span>
                          )}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-[12.5px] text-muted-foreground">
                          {r.version ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {r.tags.length === 0 && (
                            <span className="text-subtle">—</span>
                          )}
                          {r.tags.map((t) => (
                            <span
                              key={t.id}
                              className="rounded border border-border bg-muted px-1.5 py-0.5 text-[11.5px] font-medium text-muted-foreground"
                            >
                              {t.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="tabnum px-4 py-3 text-[13px] text-muted-foreground">
                        {formatDate(r.published_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <p className="font-semibold">No releases yet</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                Write your first changelog entry, or draft one from merged pull
                requests with AI.
              </p>
              <Button asChild variant="ghost">
                <Link href={newHref}>
                  <Plus />
                  New release
                </Link>
              </Button>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-subtle">
      {children}
    </th>
  );
}
