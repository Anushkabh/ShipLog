"use client";

import * as React from "react";
import { FlaskConical, Github } from "lucide-react";

import { api } from "@/lib/api";

/** Shown across the dashboard while signed into a throwaway demo workspace. */
export function DemoBanner() {
  const [leaving, setLeaving] = React.useState(false);

  async function signInForReal() {
    setLeaving(true);
    try {
      await api.logout();
    } finally {
      window.location.assign("/login");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-primary/20 bg-primary-weak px-5 py-2 text-[13px] text-primary-text">
      <FlaskConical className="size-4 flex-none" />
      <span className="min-w-0 flex-1">
        <strong className="font-semibold">You&rsquo;re in a live demo.</strong>{" "}
        This private sandbox for a fictional product, Acme Analytics, is yours to play
        with and resets in 24 hours.
      </span>
      <button
        type="button"
        onClick={signInForReal}
        disabled={leaving}
        className="inline-flex items-center gap-1.5 font-semibold underline-offset-2 hover:underline disabled:opacity-60"
      >
        <Github className="size-3.5" />
        Use it with your own repos
      </button>
    </div>
  );
}
