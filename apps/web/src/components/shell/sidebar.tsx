"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import useSWR from "swr";
import {
  ArrowLeft,
  ChevronDown,
  LayoutList,
  type LucideIcon,
  Mail,
  Plug,
  Rocket,
  Settings,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { useSession } from "@/components/auth/session";
import { OrgSwitcher } from "./org-switcher";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  soon?: boolean;
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  const content = (
    <>
      <Icon className="size-4 flex-none" />
      <span className="flex-1">{item.label}</span>
      {item.soon && (
        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-subtle">
          soon
        </span>
      )}
    </>
  );
  const base =
    "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13.5px] font-medium transition-colors";

  if (item.soon) {
    return (
      <span className={cn(base, "cursor-default text-subtle")}>{content}</span>
    );
  }
  return (
    <Link
      href={item.href}
      className={cn(
        base,
        active
          ? "bg-primary-weak font-semibold text-primary-text"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {content}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const params = useParams<{ projectId?: string }>();
  const projectId = params?.projectId;
  const { user } = useSession();

  const { data: project } = useSWR<Project>(
    projectId ? `/api/projects/${projectId}` : null,
    () => api.project(projectId!),
  );

  const projectNav: NavItem[] = projectId
    ? [
        {
          href: `/projects/${projectId}/releases`,
          label: "Releases",
          icon: LayoutList,
        },
        {
          href: `/projects/${projectId}/subscribers`,
          label: "Subscribers",
          icon: Mail,
          soon: true,
        },
        {
          href: `/projects/${projectId}/integrations`,
          label: "Integrations",
          icon: Plug,
          soon: true,
        },
        {
          href: `/projects/${projectId}/ai`,
          label: "AI drafts",
          icon: Sparkles,
          soon: true,
        },
        {
          href: `/projects/${projectId}/settings`,
          label: "Settings",
          icon: Settings,
          soon: true,
        },
      ]
    : [];

  return (
    <aside className="sticky top-0 flex h-screen w-[236px] flex-none flex-col gap-1 border-r border-border bg-sidebar p-3">
      <div className="flex items-center gap-2 px-2 pb-3 pt-1">
        <span className="grid size-[22px] place-items-center rounded-md bg-gradient-to-br from-primary to-violet-500 text-[13px] font-bold text-primary-foreground shadow-sm">
          S
        </span>
        <span className="text-[15px] font-semibold tracking-tight">
          Shiplog
        </span>
      </div>

      <OrgSwitcher />

      {projectId ? (
        <>
          <Link
            href="/projects"
            className="mt-3 flex items-center gap-2 px-2 py-1 text-[12px] font-medium text-subtle transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            All projects
          </Link>
          <div className="truncate px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-subtle">
            {project?.name ?? "Project"}
          </div>
          <nav className="flex flex-col gap-0.5">
            {projectNav.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                active={pathname.startsWith(item.href)}
              />
            ))}
          </nav>
        </>
      ) : (
        <nav className="mt-3 flex flex-col gap-0.5">
          <NavLink
            item={{ href: "/projects", label: "Projects", icon: Rocket }}
            active={pathname === "/projects"}
          />
        </nav>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-2.5 border-t border-border px-2 pt-3">
        <span className="grid size-[26px] flex-none place-items-center overflow-hidden rounded-full bg-primary text-[12px] font-semibold text-primary-foreground">
          {user?.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.image}
              alt=""
              className="size-full object-cover"
            />
          ) : (
            (user?.name ?? user?.email ?? "?").charAt(0).toUpperCase()
          )}
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block truncate text-[13px] font-semibold">
            {user?.name ?? "You"}
          </span>
          <span className="block truncate text-[11px] text-subtle">
            {user?.email}
          </span>
        </span>
        <ChevronDown className="size-3.5 flex-none text-subtle" />
      </div>
    </aside>
  );
}
