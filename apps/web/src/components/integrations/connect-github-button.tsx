"use client";

import { Github } from "lucide-react";

import { API_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * Kicks off the one-click GitHub App install flow. This is a full-page
 * navigation (not a fetch) so the session cookie rides along and GitHub can
 * redirect the browser back to our setup URL. The backend signs the state and
 * enumerates the granted repos — nothing is typed here.
 */
export function ConnectGithubButton({
  projectId,
  children,
}: {
  projectId: string;
  children?: React.ReactNode;
}) {
  function connect() {
    window.location.href = `${API_URL}/api/projects/${projectId}/integrations/github/install`;
  }

  return (
    <Button onClick={connect}>
      <Github />
      {children ?? "Connect GitHub"}
    </Button>
  );
}
