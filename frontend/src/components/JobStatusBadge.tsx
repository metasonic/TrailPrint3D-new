import type { JobStatus } from "@/types/settings";

const COPY: Record<JobStatus, { label: string; tone: string }> = {
  pending: { label: "Queued", tone: "bg-[var(--color-ink-faint)] text-[var(--color-canvas)]" },
  processing: { label: "Processing…", tone: "bg-[var(--color-warning)] text-[var(--color-canvas)]" },
  completed: { label: "Ready", tone: "bg-[var(--color-success)] text-[var(--color-canvas)]" },
  failed: { label: "Failed", tone: "bg-[var(--color-danger)] text-[var(--color-canvas)]" },
};

export function JobStatusBadge({ status, error }: { status: JobStatus | null; error?: string | null }) {
  if (!status) return null;
  const { label, tone } = COPY[status];
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`rounded-full px-2 py-1 font-semibold ${tone}`}>{label}</span>
      {status === "failed" && error && (
        <span className="text-[var(--color-danger)]" title={error}>
          {error.slice(0, 80)}
        </span>
      )}
    </div>
  );
}
