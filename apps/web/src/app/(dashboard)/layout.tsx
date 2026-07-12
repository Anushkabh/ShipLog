"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useSession } from "@/components/auth/session";
import { Sidebar } from "@/components/shell/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, loading, error } = useSession();

  React.useEffect(() => {
    if (!loading && (error?.isAuth || (!user && error))) {
      router.replace("/login");
    }
  }, [loading, user, error, router]);

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Loader2 className="size-5 animate-spin text-subtle" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1360px]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
