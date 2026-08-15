import type { Metadata } from "next";

import { getFeed, siteName } from "@/lib/feed";
import { ChangelogEntry } from "@/components/public/changelog-entry";
import { SubscribeForm } from "@/components/public/subscribe-form";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ publicKey: string }>;
}): Promise<Metadata> {
  const { publicKey } = await params;
  const feed = await getFeed(publicKey);
  const name = feed ? siteName(feed.siteUrl) : "Changelog";
  return {
    title: `${name} — Changelog`,
    description: `The latest updates and improvements to ${name}.`,
  };
}

export default async function ChangelogPage({
  params,
}: {
  params: Promise<{ publicKey: string }>;
}) {
  const { publicKey } = await params;
  const feed = await getFeed(publicKey);
  const name = feed ? siteName(feed.siteUrl) : "Changelog";

  return (
    <div>
      <div className="pb-4">
        <h1 className="text-3xl font-bold tracking-tight">What&rsquo;s new</h1>
        <p className="mt-2 text-muted-foreground">
          The latest updates, improvements, and fixes to {name}.
        </p>
      </div>

      <section
        id="subscribe"
        className="scroll-mt-20 rounded-xl border border-border bg-card p-5"
      >
        <h2 className="text-sm font-semibold">Get updates by email</h2>
        <p className="mb-3 mt-0.5 text-sm text-muted-foreground">
          One short email whenever we ship something new. No spam, unsubscribe
          anytime.
        </p>
        <SubscribeForm publicKey={publicKey} />
      </section>

      {!feed ? (
        <p className="py-16 text-center text-muted-foreground">
          This changelog is temporarily unavailable.
        </p>
      ) : feed.releases.length === 0 ? (
        <div className="py-16 text-center">
          <p className="font-semibold">No updates yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Check back soon — new releases will appear here.
          </p>
        </div>
      ) : (
        <div className="mt-4">
          {feed.releases.map((r) => (
            <ChangelogEntry key={r.url} release={r} publicKey={publicKey} />
          ))}
        </div>
      )}
    </div>
  );
}
