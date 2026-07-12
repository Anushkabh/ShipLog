"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";
import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import { useSession } from "@/components/auth/session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

export function CreateProjectDialog() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const { activeOrg } = useSession();

  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [slugEdited, setSlugEdited] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  function onNameChange(v: string) {
    setName(v);
    if (!slugEdited) setSlug(slugify(v));
  }

  function reset() {
    setName("");
    setSlug("");
    setSlugEdited(false);
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeOrg) return;
    setPending(true);
    setError(null);
    try {
      const project = await api.createProject({
        name: name.trim(),
        slug,
        organization_id: activeOrg.id,
      });
      await mutate("/api/projects");
      setOpen(false);
      reset();
      router.push(`/projects/${project.id}/releases`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't create the project. Try again.",
      );
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus />
          New project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Create a project</DialogTitle>
            <DialogDescription>
              A project is one changelog — its own public site, widget, and
              subscribers.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="Web App"
              autoFocus
              required
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              value={slug}
              onChange={(e) => {
                setSlugEdited(true);
                setSlug(slugify(e.target.value));
              }}
              placeholder="web-app"
              pattern="[a-z0-9-]+"
              required
              className="font-mono"
            />
            <p className="text-xs text-subtle">
              Lowercase letters, numbers, and hyphens. Used in the public URL.
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button
              type="submit"
              disabled={pending || !name.trim() || !slug}
            >
              {pending && <Loader2 className="animate-spin" />}
              Create project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
