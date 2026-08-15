import Link from "next/link";

import { getFeed, siteName } from "@/lib/feed";
import { ThemeToggle } from "@/components/theme-toggle";

export default async function PublicChangelogLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ publicKey: string }>;
}) {
  const { publicKey } = await params;
  const feed = await getFeed(publicKey);
  const name = feed ? siteName(feed.siteUrl) : "Changelog";
  const home = `/c/${publicKey}`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-3 px-5">
          <Link href={home} className="flex items-center gap-2.5 font-semibold">
            <span className="grid size-6 place-items-center rounded-md bg-gradient-to-br from-primary to-violet-500 text-[12px] font-bold text-primary-foreground">
              {name.charAt(0)}
            </span>
            {name}
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <Link
              href={`${home}#subscribe`}
              className="rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Subscribe
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-10">
        {children}
      </main>

      <footer className="border-t border-border py-6">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-5 text-xs text-subtle">
          <span>{name}</span>
          <span>
            Published with{" "}
            <span className="font-medium text-muted-foreground">Shiplog</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
