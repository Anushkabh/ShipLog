"use client";

import * as React from "react";
import { ArrowRight, Loader2, PlayCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * One click → a private, fully set-up demo workspace (no signup). The API
 * creates the sandbox and signs the visitor in; we then hard-navigate so the
 * dashboard boots fresh with the new session.
 */
export function TryDemoButton({
  size = "lg",
  variant = "primary",
  label = "Try the live demo",
  className,
  fullWidth = false,
}: {
  size?: "sm" | "default" | "lg";
  variant?: "primary" | "accent" | "ghost";
  label?: string;
  className?: string;
  fullWidth?: boolean;
}) {
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function start() {
    setPending(true);
    setError(null);
    try {
      const { project_id } = await api.demoLogin();
      window.location.assign(`/projects/${project_id}/setup`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't start the demo — the server may be waking up. Try again in a few seconds.",
      );
      setPending(false);
    }
  }

  return (
    <div className={fullWidth ? "flex w-full flex-col gap-1.5" : "flex flex-col items-start gap-1.5"}>
      <Button size={size} variant={variant} onClick={start} disabled={pending} className={cn(fullWidth && "w-full", className)}>
        {pending ? <Loader2 className="animate-spin" /> : <PlayCircle />}
        {pending ? "Setting up your demo…" : label}
        {!pending && <ArrowRight />}
      </Button>
      {pending && size !== "sm" && (
        <p className="text-xs text-subtle">
          Creating a private sandbox with sample data — the first visit can take up to a
          minute while the server wakes up.
        </p>
      )}
      {error && <p className="max-w-sm text-xs text-destructive">{error}</p>}
    </div>
  );
}
