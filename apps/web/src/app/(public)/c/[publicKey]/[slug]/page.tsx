import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { getRelease, siteName } from "@/lib/feed";
import { ChangelogEntry } from "@/components/public/changelog-entry";
import type { FeedRelease } from "@/lib/types";

/**
 * A single release permalink, resolved via the public single-release endpoint
 * (not the capped feed), so older entries resolve too. The product name is
 * derived from the release's own public URL.
 */
async function resolve(
  publicKey: string,
  slug: string,
): Promise<{ release: FeedRelease; name: string } | null> {
  const release = await getRelease(publicKey, slug);
  if (!release) return null;
  return { release, name: siteName(release.url) };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ publicKey: string; slug: string }>;
}): Promise<Metadata> {
  const { publicKey, slug } = await params;
  const found = await resolve(publicKey, slug);
  if (!found) return { title: "Not found" };
  return {
    title: `${found.release.title} — ${found.name}`,
  };
}

export default async function ReleasePage({
  params,
}: {
  params: Promise<{ publicKey: string; slug: string }>;
}) {
  const { publicKey, slug } = await params;
  const found = await resolve(publicKey, slug);
  if (!found) notFound();

  return (
    <div>
      <Link
        href={`/c/${publicKey}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        All updates
      </Link>

      <ChangelogEntry release={found.release} publicKey={publicKey} permalink />
    </div>
  );
}
