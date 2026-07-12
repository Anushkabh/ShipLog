"use client";

import { useParams } from "next/navigation";

import { ReleaseEditor } from "@/components/releases/editor";

export default function EditReleasePage() {
  const { projectId, releaseId } = useParams<{
    projectId: string;
    releaseId: string;
  }>();
  return <ReleaseEditor projectId={projectId} releaseId={releaseId} />;
}
