"use client";

import * as React from "react";
import useSWR from "swr";

import { api, ApiError } from "@/lib/api";
import type { Org, User } from "@/lib/types";

interface SessionValue {
  user: User | null;
  orgs: Org[];
  activeOrg: Org | null;
  setActiveOrg: (id: string) => void;
  loading: boolean;
  error: ApiError | null;
  refresh: () => void;
}

const SessionContext = React.createContext<SessionValue | null>(null);
const ACTIVE_ORG_KEY = "shiplog.activeOrg";

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const {
    data: user,
    error,
    isLoading: userLoading,
    mutate: mutateUser,
  } = useSWR<User>("/auth/me", () => api.me(), {
    shouldRetryOnError: false,
  });

  const { data: orgs, mutate: mutateOrgs } = useSWR<Org[]>(
    user ? "/auth/me/orgs" : null,
    () => api.myOrgs(),
  );

  const [activeOrgId, setActiveOrgId] = React.useState<string | null>(null);

  React.useEffect(() => {
    setActiveOrgId(localStorage.getItem(ACTIVE_ORG_KEY));
  }, []);

  const orgList = React.useMemo(() => orgs ?? [], [orgs]);

  const activeOrg = React.useMemo(() => {
    if (!orgList.length) return null;
    return orgList.find((o) => o.id === activeOrgId) ?? orgList[0];
  }, [orgList, activeOrgId]);

  const setActiveOrg = React.useCallback((id: string) => {
    localStorage.setItem(ACTIVE_ORG_KEY, id);
    setActiveOrgId(id);
  }, []);

  const value: SessionValue = {
    user: user ?? null,
    orgs: orgList,
    activeOrg,
    setActiveOrg,
    loading: userLoading,
    error: error instanceof ApiError ? error : null,
    refresh: () => {
      mutateUser();
      mutateOrgs();
    },
  };

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = React.useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
