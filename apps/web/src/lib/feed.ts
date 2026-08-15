/**
 * Server-side access to the PUBLIC widget feed. Unlike the dashboard client
 * (src/lib/api.ts), these run in React Server Components so the public
 * changelog is SSR'd for SEO. The feed endpoint is keyed by public_key and
 * needs no auth; bodyHtml is already sanitized by the API at write time.
 */

import "server-only";

import type { FeedRelease, WidgetFeed } from "./types";

// Server-reachable API origin. In prod the Next server and API may differ from
// the browser-facing origin, so allow an internal override.
const SERVER_API_URL =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

/** Fetch a project's public changelog feed. Revalidated to match the API's
 * 60s edge cache. Returns null only on a hard fetch failure (API down). */
export async function getFeed(publicKey: string): Promise<WidgetFeed | null> {
  try {
    const res = await fetch(
      `${SERVER_API_URL}/api/v1/widget/${encodeURIComponent(publicKey)}/feed`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as WidgetFeed;
  } catch {
    return null;
  }
}

/** Fetch a single published release by slug. Backed by a dedicated public
 * endpoint, so it resolves entries beyond the 20-item feed window. Returns
 * null when the release is missing, unpublished, or private (API 404). */
export async function getRelease(
  publicKey: string,
  slug: string,
): Promise<FeedRelease | null> {
  try {
    const res = await fetch(
      `${SERVER_API_URL}/api/v1/widget/${encodeURIComponent(
        publicKey,
      )}/release/${encodeURIComponent(slug)}`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as FeedRelease;
  } catch {
    return null;
  }
}

/** The API encodes a release's public URL as `{siteUrl}/{slug}`. Derive the
 * slug so permalinks can resolve an entry from the feed window. */
export function releaseSlug(release: FeedRelease): string {
  try {
    const path = new URL(release.url).pathname;
    return path.split("/").filter(Boolean).pop() ?? "";
  } catch {
    return release.url.split("/").filter(Boolean).pop() ?? "";
  }
}

/** Best-effort product name from the feed's siteUrl subdomain, for the header.
 * `https://web-app.shiplog.app` → "Web App". Falls back to "Changelog". */
export function siteName(siteUrl: string): string {
  try {
    const host = new URL(siteUrl).hostname;
    const label = host.split(".")[0];
    if (!label) return "Changelog";
    return label
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  } catch {
    return "Changelog";
  }
}
