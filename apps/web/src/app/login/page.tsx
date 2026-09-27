"use client";

import * as React from "react";
import { Github, Loader2, Rocket } from "lucide-react";

import { api, API_URL } from "@/lib/api";
import { SessionProvider, useSession } from "@/components/auth/session";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { TryDemoButton } from "@/components/demo/try-demo-button";

export default function LoginPage() {
  return (
    <SessionProvider>
      <LoginInner />
    </SessionProvider>
  );
}

// A hard navigation (not router.replace) guarantees the address bar lands on
// /projects and the dashboard boots fresh as authenticated.
function toDashboard() {
  window.location.replace("/projects");
}

function LoginInner() {
  const { user, loading } = useSession();
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // Dev login only exists on a local API (it 404s in prod), so only offer it
  // when the dashboard itself is running on localhost.
  const [isLocal, setIsLocal] = React.useState(false);
  React.useEffect(() => {
    setIsLocal(["localhost", "127.0.0.1"].includes(window.location.hostname));
  }, []);

  // Already signed in → bounce to the dashboard.
  React.useEffect(() => {
    if (!loading && user) toDashboard();
  }, [loading, user]);

  async function devLogin() {
    setPending(true);
    setError(null);
    try {
      await api.devLogin();
      toDashboard();
    } catch {
      setError("Dev login failed — is the API running on " + API_URL + "?");
      setPending(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center px-4">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 grid size-11 place-items-center rounded-xl bg-gradient-to-br from-primary to-violet-500 text-primary-foreground shadow-sm">
            <Rocket className="size-5" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">
            Sign in to Shiplog
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Draft, publish, and broadcast your release notes.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <Button asChild size="lg" className="w-full">
            <a href={api.githubLoginUrl()}>
              <Github />
              Continue with GitHub
            </a>
          </Button>

          <div className="flex items-center gap-3 py-1 text-xs text-subtle">
            <span className="h-px flex-1 bg-border" />
            or just look around
            <span className="h-px flex-1 bg-border" />
          </div>

          <TryDemoButton variant="accent" label="Try the live demo — no signup" fullWidth />

          {isLocal && (
            <Button
              variant="ghost"
              size="lg"
              className="w-full"
              onClick={devLogin}
              disabled={pending}
            >
              {pending ? <Loader2 className="animate-spin" /> : <Rocket />}
              Continue as Dev User (local only)
            </Button>
          )}

          {error && (
            <p className="text-center text-sm text-destructive">{error}</p>
          )}
        </div>
      </div>
    </main>
  );
}
