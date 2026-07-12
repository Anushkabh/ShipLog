"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Github, Loader2, Rocket } from "lucide-react";

import { api, API_URL } from "@/lib/api";
import { useSession } from "@/components/auth/session";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, refresh } = useSession();
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Already signed in → bounce to the dashboard.
  React.useEffect(() => {
    if (!loading && user) router.replace("/projects");
  }, [loading, user, router]);

  async function devLogin() {
    setPending(true);
    setError(null);
    try {
      await api.devLogin();
      refresh();
      router.replace("/projects");
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
            local development
            <span className="h-px flex-1 bg-border" />
          </div>

          <Button
            variant="ghost"
            size="lg"
            className="w-full"
            onClick={devLogin}
            disabled={pending}
          >
            {pending ? <Loader2 className="animate-spin" /> : <Rocket />}
            Continue as Dev User
          </Button>

          {error && (
            <p className="text-center text-sm text-destructive">{error}</p>
          )}
        </div>

        <p className="mt-8 text-center text-xs text-subtle">
          Dev login is available only when the API runs with{" "}
          <code className="font-mono">env=local</code>.
        </p>
      </div>
    </main>
  );
}
