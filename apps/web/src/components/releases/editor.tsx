"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { Check, Loader2, Send, Sparkles } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Project, Release } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/releases/status-badge";
import { MarkdownPreview } from "@/components/releases/markdown-preview";

function slugify(v: string) {
  return v
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 128);
}

export function ReleaseEditor({
  projectId,
  releaseId,
}: {
  projectId: string;
  releaseId?: string;
}) {
  const router = useRouter();
  const { mutate: globalMutate } = useSWRConfig();

  const { data: project } = useSWR<Project>(
    `/api/projects/${projectId}`,
    () => api.project(projectId),
  );
  const { data: existing } = useSWR<Release>(
    releaseId ? `/api/projects/${projectId}/releases/${releaseId}` : null,
    () => api.release(projectId, releaseId!),
  );

  const [currentId, setCurrentId] = React.useState<string | undefined>(
    releaseId,
  );
  const [title, setTitle] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [slugEdited, setSlugEdited] = React.useState(false);
  const [version, setVersion] = React.useState("");
  const [body, setBody] = React.useState("");
  const [status, setStatus] = React.useState<Release["status"]>("draft");
  const [aiGenerated, setAiGenerated] = React.useState(false);
  const [broadcast, setBroadcast] = React.useState(true);

  const [saving, setSaving] = React.useState(false);
  const [publishing, setPublishing] = React.useState(false);
  const [savedAt, setSavedAt] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // Hydrate from a loaded release exactly once.
  const hydrated = React.useRef(false);
  React.useEffect(() => {
    if (existing && !hydrated.current) {
      hydrated.current = true;
      setTitle(existing.title);
      setSlug(existing.slug);
      setSlugEdited(true);
      setVersion(existing.version ?? "");
      setBody(existing.body_markdown);
      setStatus(existing.status);
      setAiGenerated(existing.ai_generated);
    }
  }, [existing]);

  const isNew = !currentId;
  const isPublished = status === "published";

  function onTitleChange(v: string) {
    setTitle(v);
    if (isNew && !slugEdited) setSlug(slugify(v));
  }

  async function persist(): Promise<Release | null> {
    if (currentId) {
      return api.updateRelease(projectId, currentId, {
        title: title.trim(),
        version: version.trim() || null,
        body_markdown: body,
      });
    }
    const created = await api.createRelease(projectId, {
      title: title.trim(),
      slug,
      version: version.trim() || null,
      body_markdown: body,
    });
    setCurrentId(created.id);
    // Reflect the real URL without a reload so refresh/back behaves.
    window.history.replaceState(
      null,
      "",
      `/projects/${projectId}/releases/${created.id}`,
    );
    return created;
  }

  async function saveDraft() {
    setSaving(true);
    setError(null);
    try {
      const r = await persist();
      if (r) setStatus(r.status);
      await globalMutate(`/api/projects/${projectId}/releases`);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }

  async function publish() {
    setPublishing(true);
    setError(null);
    try {
      const saved = await persist();
      const id = saved?.id ?? currentId;
      if (!id) throw new Error("no release id");
      await api.publishRelease(projectId, id, { broadcast_email: broadcast });
      await globalMutate(`/api/projects/${projectId}/releases`);
      router.push(`/projects/${projectId}/releases`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't publish.");
      setPublishing(false);
    }
  }

  const canSave = title.trim().length > 0 && (!isNew || slug.length > 0);

  return (
    <>
      <Topbar
        crumbs={[
          {
            label: project?.name ?? "Project",
            href: `/projects/${projectId}/releases`,
          },
          { label: isNew ? "New release" : title || "Untitled" },
        ]}
      />

      <div className="flex min-h-0 flex-1 flex-col">
        {/* Header / meta */}
        <div className="flex flex-col gap-3 border-b border-border p-6 pb-4">
          <div className="flex items-center gap-3">
            <input
              value={title}
              onChange={(e) => onTitleChange(e.target.value)}
              placeholder="Release title"
              className="min-w-0 flex-1 bg-transparent text-xl font-bold tracking-tight outline-none placeholder:text-subtle"
            />
            <StatusBadge status={status} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-subtle">
              <span className="font-mono text-subtle">v</span>
              <Input
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="2.4.0"
                className="h-7 w-28 font-mono text-[13px]"
              />
            </label>
            <span className="text-subtle">·</span>
            <label className="flex items-center gap-1.5 text-xs text-subtle">
              slug
              <Input
                value={slug}
                onChange={(e) => {
                  setSlugEdited(true);
                  setSlug(slugify(e.target.value));
                }}
                placeholder="release-slug"
                disabled={!isNew}
                className="h-7 w-44 font-mono text-[13px] disabled:opacity-70"
              />
            </label>
            {aiGenerated && (
              <span className="ml-1 inline-flex items-center gap-1 rounded bg-primary-weak px-1.5 py-0.5 text-[11px] font-semibold text-primary-text">
                <Sparkles className="size-3" />
                AI draft
              </span>
            )}
          </div>
        </div>

        {/* Split pane */}
        <div className="grid min-h-[440px] flex-1 grid-cols-1 md:grid-cols-2">
          <div className="flex min-w-0 flex-col border-b border-border md:border-b-0 md:border-r">
            <PaneHead>
              Markdown
              <Button
                variant="accent"
                size="sm"
                className="ml-auto h-7"
                disabled
                title="AI drafting arrives in the next milestone"
              >
                <Sparkles className="size-3.5" />
                Draft from merged PRs
              </Button>
            </PaneHead>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={"# What's new\n\n- Describe the change…"}
              spellCheck={false}
              className="min-h-[360px] flex-1 resize-none bg-transparent p-5 font-mono text-[13px] leading-relaxed outline-none placeholder:text-subtle"
            />
          </div>
          <div className="flex min-w-0 flex-col">
            <PaneHead>Preview</PaneHead>
            <div className="flex-1 overflow-auto p-5">
              <MarkdownPreview source={body} />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t border-border bg-background/90 px-6 py-3 backdrop-blur">
          <label className="flex cursor-pointer items-center gap-2 text-[13px] text-muted-foreground">
            <input
              type="checkbox"
              checked={broadcast}
              onChange={(e) => setBroadcast(e.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            Email subscribers on publish
          </label>

          {error && <span className="text-[13px] text-destructive">{error}</span>}
          {!error && savedAt && (
            <span className="flex items-center gap-1 text-[13px] text-status-published">
              <Check className="size-3.5" />
              Saved {savedAt}
            </span>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              onClick={saveDraft}
              disabled={!canSave || saving || publishing}
            >
              {saving && <Loader2 className="animate-spin" />}
              Save draft
            </Button>
            <Button
              onClick={publish}
              disabled={!canSave || publishing || saving}
            >
              {publishing ? <Loader2 className="animate-spin" /> : <Send />}
              {isPublished ? "Republish" : "Publish now"}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}

function PaneHead({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 border-b border-border bg-muted/60 px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-subtle",
      )}
    >
      {children}
    </div>
  );
}
