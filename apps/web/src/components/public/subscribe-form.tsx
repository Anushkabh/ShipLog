"use client";

import * as React from "react";
import { Check, Loader2, Mail } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "sent" }
  | { kind: "already" }
  | { kind: "error"; message: string };

export function SubscribeForm({ publicKey }: { publicKey: string }) {
  const [email, setEmail] = React.useState("");
  const [state, setState] = React.useState<State>({ kind: "idle" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState({ kind: "loading" });
    try {
      const res = await api.subscribe(publicKey, email.trim());
      setState({
        kind: res.status === "already_subscribed" ? "already" : "sent",
      });
    } catch (err) {
      setState({
        kind: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Something went wrong. Please try again.",
      });
    }
  }

  if (state.kind === "sent" || state.kind === "already") {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-status-published/30 bg-status-published-bg px-4 py-3 text-sm text-status-published">
        <Check className="size-4 flex-none" />
        {state.kind === "sent"
          ? "Check your inbox to confirm your subscription."
          : "You're already subscribed — nothing more to do."}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
          <Input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="pl-9"
            disabled={state.kind === "loading"}
          />
        </div>
        <Button type="submit" disabled={state.kind === "loading" || !email.trim()}>
          {state.kind === "loading" && <Loader2 className="animate-spin" />}
          Subscribe
        </Button>
      </div>
      {state.kind === "error" && (
        <p className="text-sm text-destructive">{state.message}</p>
      )}
    </form>
  );
}
