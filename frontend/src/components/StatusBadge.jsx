import { cn, titleize } from "../lib/utils";

const toneByStatus = {
  active: "good",
  completed: "good",
  paid: "good",
  applied: "good",
  offer: "good",
  interview: "medium",
  monthly: "medium",
  yearly: "medium",
  processing: "medium",
  pending: "medium",
  ready: "good",
  healthy: "good",
  saved: "muted",
  missing: "muted",
  free: "muted",
  archived: "muted",
  issue: "medium",
  blocked: "low",
  canceled: "low",
  rejected: "low",
  failed: "low",
  empty_text: "low",
  unsupported_structure: "low"
};

export function StatusBadge({ value, tone, className }) {
  const resolvedTone = tone ?? toneByStatus[value] ?? "muted";

  return (
    <span className={cn("status-badge", `tone-${resolvedTone}`, className)}>
      {titleize(value)}
    </span>
  );
}
