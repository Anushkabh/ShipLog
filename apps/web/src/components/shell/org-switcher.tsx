"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { useSession } from "@/components/auth/session";

function initials(name: string) {
  return name.trim().charAt(0).toUpperCase() || "?";
}

export function OrgSwitcher() {
  const { orgs, activeOrg, setActiveOrg } = useSession();
  const [open, setOpen] = React.useState(false);

  if (!activeOrg) {
    return <div className="h-[38px] animate-pulse rounded-md bg-muted" />;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-md border border-border bg-card px-2 py-1.5 text-left transition-colors hover:bg-muted"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="grid size-5 flex-none place-items-center rounded bg-primary text-[11px] font-bold text-primary-foreground">
          {initials(activeOrg.name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold">
            {activeOrg.name}
          </span>
          <span className="block truncate text-[11px] capitalize text-subtle">
            {activeOrg.role ?? "member"}
          </span>
        </span>
        <ChevronsUpDown className="size-3.5 flex-none text-subtle" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <ul
            role="listbox"
            className="absolute left-0 right-0 top-[calc(100%+4px)] z-20 overflow-hidden rounded-md border border-border bg-popover p-1 shadow-lg"
          >
            {orgs.map((org) => (
              <li key={org.id}>
                <button
                  role="option"
                  aria-selected={org.id === activeOrg.id}
                  onClick={() => {
                    setActiveOrg(org.id);
                    setOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-muted"
                >
                  <span className="grid size-5 flex-none place-items-center rounded bg-muted text-[11px] font-bold text-muted-foreground">
                    {initials(org.name)}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{org.name}</span>
                  {org.id === activeOrg.id && (
                    <Check className="size-3.5 flex-none text-primary-text" />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
