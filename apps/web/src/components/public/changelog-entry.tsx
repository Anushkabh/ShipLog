import Link from "next/link";

import { formatDate } from "@/lib/utils";
import { releaseSlug } from "@/lib/feed";
import type { FeedRelease } from "@/lib/types";

/**
 * One changelog entry. On the index page the title links to its permalink; on
 * the permalink page it renders as a plain heading. bodyHtml is sanitized by
 * the API at write time, so it is rendered verbatim (see widget.py).
 */
export function ChangelogEntry({
  release,
  publicKey,
  permalink,
}: {
  release: FeedRelease;
  publicKey: string;
  permalink?: boolean;
}) {
  const href = `/c/${publicKey}/${releaseSlug(release)}`;

  return (
    <article className="border-b border-border py-10 first:pt-0 last:border-0">
      <time className="tabnum block text-[13px] font-medium text-subtle">
        {formatDate(release.publishedAt)}
      </time>

      {permalink ? (
        <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-foreground">
          {release.title}
        </h1>
      ) : (
        <h2 className="mt-1.5 text-xl font-bold tracking-tight">
          <Link href={href} className="transition-colors hover:text-primary-text">
            {release.title}
          </Link>
        </h2>
      )}

      {release.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {release.tags.map((t) => (
            <span
              key={t.name}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
            >
              <span
                className="size-1.5 rounded-full"
                style={{ backgroundColor: t.color }}
              />
              {t.name}
            </span>
          ))}
        </div>
      )}

      <div
        className="changelog-prose mt-5"
        dangerouslySetInnerHTML={{ __html: release.bodyHtml }}
      />
    </article>
  );
}
