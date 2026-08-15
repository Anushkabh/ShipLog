"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Check, KeyRound, Loader2, Lock, Sparkles } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AiProvider, CredentialStatus, Project } from "@/lib/types";
import { Topbar } from "@/components/shell/topbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

const PROVIDERS: { value: AiProvider; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
  { value: "groq", label: "Groq" },
];

export default function AiSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: project, mutate: mutateProject } = useSWR<Project>(
    `/api/projects/${projectId}`,
    () => api.project(projectId),
  );
  const {
    data: cred,
    isLoading,
    mutate,
  } = useSWR<CredentialStatus>(`/api/projects/${projectId}/ai/credential`, () =>
    api.aiCredential(projectId),
  );

  const [provider, setProvider] = React.useState<AiProvider>("openai");
  const [apiKey, setApiKey] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Product context that grounds the AI's voice.
  const [summary, setSummary] = React.useState("");
  const [audience, setAudience] = React.useState("");
  const [tone, setTone] = React.useState("");
  const [profileSaving, setProfileSaving] = React.useState(false);
  const [profileSaved, setProfileSaved] = React.useState(false);
  const [inferring, setInferring] = React.useState(false);
  const [inferNote, setInferNote] = React.useState<string | null>(null);
  const profileHydrated = React.useRef(false);

  React.useEffect(() => {
    if (cred?.provider) setProvider(cred.provider);
  }, [cred?.provider]);

  React.useEffect(() => {
    if (project && !profileHydrated.current) {
      profileHydrated.current = true;
      setSummary(project.product_summary ?? "");
      setAudience(project.audience ?? "");
      setTone(project.tone ?? "");
    }
  }, [project]);

  async function autofill() {
    setInferring(true);
    setInferNote(null);
    setError(null);
    try {
      const p = await api.inferProjectProfile(projectId);
      setSummary(p.product_summary ?? "");
      setAudience(p.audience ?? "");
      setTone(p.tone ?? "");
      setInferNote("Drafted from your repo’s README — review and edit, then save.");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn’t analyze your repo. Try again.",
      );
    } finally {
      setInferring(false);
    }
  }

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileSaved(false);
    setError(null);
    try {
      await mutateProject(
        api.updateProjectProfile(projectId, {
          product_summary: summary.trim() || null,
          audience: audience.trim() || null,
          tone: tone.trim() || null,
        }),
      );
      setProfileSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Couldn't save product context.",
      );
    } finally {
      setProfileSaving(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      await api.setAiCredential(projectId, { provider, api_key: apiKey.trim() });
      await mutate();
      setApiKey("");
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? "Only project admins can change the AI provider key."
            : err.message
          : "Couldn't save the key. Try again.",
      );
    } finally {
      setPending(false);
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
          { label: "AI drafts" },
        ]}
      />
      <div className="flex max-w-2xl flex-col gap-5 p-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight">AI drafts</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Bring your own provider key. Shiplog drafts release notes from your
            connected repos&rsquo; merged PRs — you always review before
            publishing.
          </p>
        </div>

        {/* Status */}
        {isLoading ? (
          <Skeleton className="h-16" />
        ) : (
          <Card>
            <CardContent className="flex items-center gap-3 p-4">
              <span
                className={cn(
                  "grid size-9 flex-none place-items-center rounded-md",
                  cred?.configured
                    ? "bg-status-published-bg text-status-published"
                    : "bg-muted text-subtle",
                )}
              >
                {cred?.configured ? (
                  <Check className="size-4.5" />
                ) : (
                  <KeyRound className="size-4.5" />
                )}
              </span>
              <div className="flex-1">
                <div className="text-sm font-semibold">
                  {cred?.configured
                    ? `Connected — ${
                        PROVIDERS.find((p) => p.value === cred.provider)
                          ?.label ?? cred.provider
                      }`
                    : "No provider configured"}
                </div>
                <div className="text-xs text-subtle">
                  {cred?.configured
                    ? "The key is stored AES-256-GCM encrypted at rest."
                    : "Add a provider key below to enable AI drafting."}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Key form */}
        <Card>
          <CardHeader>
            <CardTitle>{cred?.configured ? "Replace key" : "Add key"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={save} className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="provider">Provider</Label>
                <select
                  id="provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as AiProvider)}
                  className="h-9 rounded-md border border-input bg-card px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="key">API key</Label>
                <Input
                  id="key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={cred?.configured ? "Enter a new key to replace" : "sk-…"}
                  autoComplete="off"
                  required
                  className="font-mono"
                />
                <p className="flex items-center gap-1.5 text-xs text-subtle">
                  <Lock className="size-3" />
                  Encrypted before it touches the database. Never shown again.
                </p>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <div className="flex items-center gap-3">
                <Button type="submit" disabled={pending || !apiKey.trim()}>
                  {pending && <Loader2 className="animate-spin" />}
                  Save key
                </Button>
                {saved && (
                  <span className="flex items-center gap-1 text-sm text-status-published">
                    <Check className="size-3.5" />
                    Saved
                  </span>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Product context — grounds the AI voice */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>Product context</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Optional, but it&rsquo;s what makes drafts sound like{" "}
                  <span className="font-medium text-foreground">your</span>{" "}
                  product instead of generic. Fed to the AI on every draft.
                </p>
              </div>
              <Button
                type="button"
                variant="subtle"
                size="sm"
                onClick={autofill}
                disabled={inferring}
                className="flex-none"
              >
                {inferring ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                Auto-fill from repo
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={saveProfile} className="grid gap-4">
              {inferNote && (
                <p className="flex items-center gap-1.5 rounded-md bg-primary-weak px-3 py-2 text-xs text-primary-text">
                  <Sparkles className="size-3 flex-none" />
                  {inferNote}
                </p>
              )}
              <div className="grid gap-2">
                <Label htmlFor="summary">What is this product?</Label>
                <Textarea
                  id="summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="e.g. Acme Analytics is a self-serve product-analytics dashboard for SaaS teams to track usage, funnels, and revenue."
                  rows={3}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="audience">Who reads your release notes?</Label>
                <Input
                  id="audience"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="e.g. Product managers and founders at SaaS companies"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tone">Voice &amp; tone</Label>
                <Input
                  id="tone"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  placeholder="e.g. Friendly, confident, concrete — benefit-led, no jargon"
                />
              </div>
              <div className="flex items-center gap-3">
                <Button type="submit" disabled={profileSaving}>
                  {profileSaving && <Loader2 className="animate-spin" />}
                  Save context
                </Button>
                {profileSaved && (
                  <span className="flex items-center gap-1 text-sm text-status-published">
                    <Check className="size-3.5" />
                    Saved
                  </span>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        {/* How it works */}
        <Card>
          <CardContent className="flex gap-3 p-4">
            <Sparkles className="size-4 flex-none text-primary-text" />
            <p className="text-sm text-muted-foreground">
              Once a key is set, open any release and choose{" "}
              <span className="font-medium text-foreground">
                Draft from merged PRs
              </span>{" "}
              to stream a draft from PRs merged since your last release. Connect
              repos on the{" "}
              <Link
                href={`/projects/${projectId}/integrations`}
                className="font-medium text-primary-text underline"
              >
                Integrations
              </Link>{" "}
              page first.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
