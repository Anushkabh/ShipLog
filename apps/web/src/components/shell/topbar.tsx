"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { useSession } from "@/components/auth/session";

export interface Crumb {
  label: string;
  href?: string;
  muted?: boolean;
}

export function Topbar({ crumbs = [] }: { crumbs?: Crumb[] }) {
  const router = useRouter();
  const { activeOrg, refresh } = useSession();

  const trail: Crumb[] = [
    { label: activeOrg?.name ?? "Workspace", muted: true },
    ...crumbs,
  ];

  async function signOut() {
    try {
      await api.logout();
    } finally {
      refresh();
      router.replace("/login");
    }
  }

  return (
    <header className="sticky top-0 z-10 flex h-[52px] flex-none items-center gap-3 border-b border-border bg-background/80 px-6 backdrop-blur">
      <nav className="flex items-center gap-2 text-sm">
        {trail.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-subtle">/</span>}
            <span
              className={
                i === trail.length - 1
                  ? "font-semibold text-foreground"
                  : c.muted
                    ? "text-muted-foreground"
                    : "font-medium text-foreground"
              }
            >
              {c.label}
            </span>
          </React.Fragment>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-1.5">
        <ThemeToggle />
        <Button
          variant="subtle"
          size="icon"
          onClick={signOut}
          aria-label="Sign out"
        >
          <LogOut />
        </Button>
      </div>
    </header>
  );
}
