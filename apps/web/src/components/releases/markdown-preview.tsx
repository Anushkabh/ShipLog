"use client";

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders markdown to a styled preview. react-markdown does not use
 * dangerouslySetInnerHTML, so this is safe for author-entered content. The
 * public site renders the server's nh3-sanitized body_html instead.
 */
export function MarkdownPreview({ source }: { source: string }) {
  if (!source.trim()) {
    return (
      <p className="text-sm italic text-subtle">
        Nothing to preview yet. Start writing on the left.
      </p>
    );
  }

  return (
    <div className="text-[14px] leading-relaxed text-muted-foreground">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => (
            <h1
              className="mb-1.5 mt-5 text-xl font-semibold tracking-tight text-foreground first:mt-0"
              {...p}
            />
          ),
          h2: (p) => (
            <h2
              className="mb-1.5 mt-5 text-base font-semibold tracking-tight text-foreground first:mt-0"
              {...p}
            />
          ),
          h3: (p) => (
            <h3
              className="mb-1 mt-4 text-sm font-semibold text-foreground"
              {...p}
            />
          ),
          p: (p) => <p className="mb-2.5" {...p} />,
          ul: (p) => (
            <ul className="mb-2.5 list-disc space-y-1 pl-5" {...p} />
          ),
          ol: (p) => (
            <ol className="mb-2.5 list-decimal space-y-1 pl-5" {...p} />
          ),
          li: (p) => <li className="pl-0.5" {...p} />,
          a: (p) => (
            <a className="font-medium text-primary-text underline" {...p} />
          ),
          strong: (p) => (
            <strong className="font-semibold text-foreground" {...p} />
          ),
          code: (p) => (
            <code
              className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[12px] text-foreground"
              {...p}
            />
          ),
          pre: (p) => (
            <pre
              className="mb-2.5 overflow-x-auto rounded-md border border-border bg-muted p-3 font-mono text-[12.5px] text-foreground"
              {...p}
            />
          ),
          blockquote: (p) => (
            <blockquote
              className="mb-2.5 border-l-2 border-border pl-3 italic"
              {...p}
            />
          ),
          hr: () => <hr className="my-4 border-border" />,
        }}
      >
        {source}
      </Markdown>
    </div>
  );
}
