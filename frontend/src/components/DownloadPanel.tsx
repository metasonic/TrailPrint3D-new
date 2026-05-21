/**
 * Export-format picker + Download button. Phase 5 stub: clicking download
 * invokes the supplied `onExport` callback (no-op here). Phase 7 wires this
 * to POST /api/v1/export and triggers a browser download once the job is done.
 */

import { useAppState } from "@/state/AppState";
import type { ExportFormat } from "@/types/settings";

const FORMATS: { value: ExportFormat; label: string; desc: string }[] = [
  { value: "stl", label: "STL", desc: "Universal 3D printing" },
  { value: "obj", label: "OBJ", desc: "Wavefront, with materials" },
  { value: "3mf", label: "3MF", desc: "Modern, multi-material" },
  { value: "glb", label: "GLB", desc: "glTF binary, viewer-friendly" },
];

interface Props {
  onExport?: (fmt: ExportFormat) => void;
  disabled?: boolean;
}

export function DownloadPanel({ onExport, disabled }: Props) {
  const { exportFormat, setExportFormat, gpx } = useAppState();
  const noFile = !gpx;
  return (
    <div className="flex flex-col gap-3 rounded-(--radius-md) bg-[var(--color-surface)] p-5">
      <header>
        <h2 className="text-base font-semibold">Download</h2>
        <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
          {noFile ? "Upload a GPX to enable export." : "Choose a format and export."}
        </p>
      </header>
      <div className="grid grid-cols-2 gap-2">
        {FORMATS.map((f) => (
          <label
            key={f.value}
            className={[
              "cursor-pointer rounded-(--radius-sm) border px-3 py-2 text-sm transition-colors",
              exportFormat === f.value
                ? "border-[var(--color-accent)] bg-[var(--color-surface-raised)]"
                : "border-[var(--color-edge)] hover:border-[var(--color-accent-strong)]",
            ].join(" ")}
          >
            <input
              type="radio"
              name="format"
              value={f.value}
              checked={exportFormat === f.value}
              onChange={() => setExportFormat(f.value)}
              className="sr-only"
            />
            <div className="font-semibold text-[var(--color-ink-primary)]">{f.label}</div>
            <div className="text-[10px] text-[var(--color-ink-faint)]">{f.desc}</div>
          </label>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onExport?.(exportFormat)}
        disabled={disabled || noFile}
        className="inline-flex items-center justify-center rounded-(--radius-sm) bg-[var(--color-success)] px-4 py-2 text-sm font-semibold text-[var(--color-canvas)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Export
      </button>
    </div>
  );
}
