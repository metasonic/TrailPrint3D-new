import { useCallback, useRef, useState } from "react";
import { useAppState } from "@/state/AppState";

interface Props {
  onUpload?: (file: File) => void;
}

export function UploadForm({ onUpload }: Props) {
  const { gpx, setGpx } = useAppState();
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = useCallback(
    (file: File | null | undefined) => {
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".gpx")) {
        // Phase 5 keeps UX feedback inline; Phase 6 will surface server-side validation too.
        alert("Please choose a .gpx file");
        return;
      }
      setGpx(file);
      onUpload?.(file);
    },
    [setGpx, onUpload],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handleFile(e.dataTransfer.files?.[0]);
      }}
      className={[
        "rounded-(--radius-md) border-2 border-dashed p-6 text-center transition-colors",
        drag
          ? "border-[var(--color-accent)] bg-[var(--color-surface-raised)]"
          : "border-[var(--color-edge)] bg-[var(--color-surface)]",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".gpx,application/gpx+xml"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <p className="text-sm text-[var(--color-ink-muted)]">
        {gpx ? (
          <>
            Loaded: <span className="text-[var(--color-ink-primary)]">{gpx.name}</span>
            {" — "}
            <button
              type="button"
              onClick={() => setGpx(null)}
              className="underline text-[var(--color-accent)] hover:text-[var(--color-accent-strong)]"
            >
              clear
            </button>
          </>
        ) : (
          <>Drop a .gpx file here, or</>
        )}
      </p>
      {!gpx && (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-3 inline-flex items-center rounded-(--radius-sm) bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-canvas)] hover:bg-[var(--color-accent-strong)]"
        >
          Choose file
        </button>
      )}
    </div>
  );
}
