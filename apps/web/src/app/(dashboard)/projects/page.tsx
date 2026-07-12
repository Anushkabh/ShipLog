"use client";

import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, Globe, Rocket } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { Project } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";

export default function ProjectsPage() {
  const { data: projects, isLoading } = useSWR<Project[]>(
    "/api/projects",
    () => api.projects(),
  );

  return (
    <>
      <Topbar crumbs={[{ label: "Projects" }]} />
      <div className="flex flex-col gap-6 p-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Projects</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Each project is an independent changelog with its own site and
              subscribers.
            </p>
          </div>
          <CreateProjectDialog />
        </div>

        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : projects && projects.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}/releases`}>
                <Card className="group h-full p-4 transition-colors hover:border-border-strong hover:bg-muted/50">
                  <div className="flex items-start justify-between">
                    <span className="grid size-9 place-items-center rounded-md bg-primary-weak text-primary-text">
                      <Rocket className="size-4.5" />
                    </span>
                    <ArrowRight className="size-4 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <div className="mt-3 font-semibold tracking-tight">
                    {p.name}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-xs text-subtle">
                    <Globe className="size-3" />
                    <span className="font-mono">{p.slug}</span>
                  </div>
                  <div className="mt-3 text-xs text-subtle">
                    Created {formatDate(p.created_at)}
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <Card className="flex flex-col items-center gap-3 border-dashed py-14 text-center">
            <span className="grid size-11 place-items-center rounded-xl bg-primary-weak text-primary-text">
              <Rocket className="size-5" />
            </span>
            <div>
              <p className="font-semibold">No projects yet</p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Create your first project to start drafting release notes.
              </p>
            </div>
            <CreateProjectDialog />
          </Card>
        )}
      </div>
    </>
  );
}
