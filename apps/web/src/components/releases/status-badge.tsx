import { cn } from "@/lib/utils";
import type { ReleaseStatus } from "@/lib/types";

const STATUS: Record<
  ReleaseStatus,
  { label: string; className: string; dot: string }
> = {
  draft: {
    label: "Draft",
    className: "text-status-draft bg-status-draft-bg",
    dot: "bg-status-draft",
  },
  scheduled: {
    label: "Scheduled",
    className: "text-status-scheduled bg-status-scheduled-bg",
    dot: "bg-status-scheduled",
  },
  published: {
    label: "Published",
    className: "text-status-published bg-status-published-bg",
    dot: "bg-status-published",
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: ReleaseStatus;
  className?: string;
}) {
  const s = STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full py-0.5 pl-2 pr-2.5 text-xs font-semibold",
        s.className,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}
