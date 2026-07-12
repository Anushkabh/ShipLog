"use client";

import { useParams } from "next/navigation";

import { ReleaseEditor } from "@/components/releases/editor";

export default function NewReleasePage() {
  const { projectId } = useParams<{ projectId: string }>();
  return <ReleaseEditor projectId={projectId} />;
}
