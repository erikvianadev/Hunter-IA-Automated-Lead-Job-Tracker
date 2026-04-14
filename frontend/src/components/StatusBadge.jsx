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
  priority_1: "warning",
  priority_2: "medium",
  priority_3: "muted",
  ready: "good",
  healthy: "good",
  saved: "muted",
  missing: "muted",
  free: "muted",
  archived: "muted",
  issue: "warning",
  blocked: "blocked",
  canceled: "low",
  rejected: "low",
  failed: "low",
  empty_text: "warning",
  unsupported_structure: "warning",
  locked: "premium"
};

export function StatusBadge({ value, label, tone, className, title }) {
  const resolvedTone = tone ?? toneByStatus[value] ?? "muted";
  const resolvedLabel = label ?? titleize(value);

  return (
    <span className={cn("status-badge", `tone-${resolvedTone}`, className)} title={title}>
      {resolvedLabel}
    </span>
  );
}
