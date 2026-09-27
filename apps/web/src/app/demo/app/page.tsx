"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, BarChart3, Bell, Users, Wallet, Zap } from "lucide-react";

import { API_URL } from "@/lib/api";
import { useOrigin } from "@/lib/use-origin";

/**
 * A pretend customer app ("Acme Analytics") that embeds the real Shiplog
 * widget for a project's public key — so a demo visitor can see what their end
 * users would see: a "What's new" launcher with an unread badge and a popover
 * of published releases.
 */
export default function DemoAppPage() {
  return (
    <React.Suspense fallback={null}>
      <DemoApp />
    </React.Suspense>
  );
}

function DemoApp() {
  const key = useSearchParams().get("key");

  // Inject the one-line embed exactly as a customer would.
  React.useEffect(() => {
    if (!key) return;
    const script = document.createElement("script");
    script.src = "/widget.js";
    script.async = true;
    script.setAttribute("data-key", key);
    // Same origin in prod (Vercel proxies /api); the API directly in local dev.
    script.setAttribute("data-api", API_URL);
    script.setAttribute("data-accent", "#6366f1");
    document.body.appendChild(script);

    // Pop the widget open once it has rendered, so visitors see the payoff
    // without hunting for the launcher. (Its shadow root is open by design.)
    let tries = 0;
    const opener = window.setInterval(() => {
      const launcher = document
        .getElementById("shiplog-widget")
        ?.shadowRoot?.querySelector<HTMLButtonElement>(".launcher");
      if (launcher) {
        window.clearInterval(opener);
        window.setTimeout(() => launcher.click(), 900);
      } else if (++tries > 40) {
        window.clearInterval(opener);
      }
    }, 150);

    return () => {
      window.clearInterval(opener);
      script.remove();
      document.getElementById("shiplog-widget")?.remove();
    };
  }, [key]);

  const origin = useOrigin();
  const snippet = `<script src="${origin}/widget.js" data-key="${key ?? "YOUR_KEY"}" async></script>`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Explainer strip (not part of the pretend app) */}
      <div className="bg-slate-900 px-5 py-3 text-sm text-slate-100">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2">
          <Link href="/projects" className="inline-flex flex-none items-center gap-1 text-slate-300 hover:text-white">
            <ArrowLeft className="size-4" /> Back to Shiplog
          </Link>
          <span className="min-w-[280px] flex-1">
            This is a <strong>pretend customer app</strong>. The{" "}
            <strong>&ldquo;What&rsquo;s new&rdquo;</strong> button in the bottom-right corner is
            Shiplog&rsquo;s embeddable widget, showing your published releases live.
          </span>
          <code className="hidden max-w-md truncate rounded bg-slate-800 px-2 py-1 font-mono text-xs text-slate-300 xl:block">
            {snippet}
          </code>
        </div>
      </div>

      {/* The pretend app */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-5">
          <span className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-md bg-indigo-600 text-white">
              <BarChart3 className="size-4" />
            </span>
            Acme Analytics
          </span>
          <nav className="hidden gap-5 text-sm text-slate-500 sm:flex">
            <span className="font-medium text-slate-900">Dashboard</span>
            <span>Funnels</span>
            <span>Cohorts</span>
            <span>Reports</span>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <Bell className="size-4 text-slate-400" />
            <span className="grid size-8 place-items-center rounded-full bg-slate-200 text-xs font-semibold">
              JD
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <h1 className="text-xl font-semibold">Good morning, Jamie</h1>
        <p className="mt-1 text-sm text-slate-500">Here&rsquo;s how your product did this week.</p>

        {!key && (
          <p className="mt-6 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
            No project key in the URL — open this page from a project&rsquo;s Get started page to
            load its releases.
          </p>
        )}

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Kpi icon={Users} label="Active users" value="12,480" delta="+8.2%" />
          <Kpi icon={Zap} label="Activation rate" value="41.3%" delta="+2.1 pts" />
          <Kpi icon={Wallet} label="MRR" value="$48.2k" delta="+5.4%" />
        </div>

        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Weekly active users</h2>
            <span className="text-xs text-slate-400">Last 12 weeks</span>
          </div>
          <div className="flex h-48 items-end gap-2">
            {[38, 42, 40, 47, 51, 49, 56, 60, 58, 66, 71, 78].map((h, i) => (
              <div
                key={i}
                className="flex-1 rounded-t bg-indigo-500/80"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  delta,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  delta: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Icon className="size-4" /> {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs font-medium text-emerald-600">{delta} vs last week</div>
    </div>
  );
}
