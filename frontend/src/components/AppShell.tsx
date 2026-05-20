/**
 * Frontend shell composition.
 *
 * Phase 6 wires the upload + regenerate flows to the backend:
 *   1. User drops a GPX → POST /api/v1/preview with default settings →
 *      poll GET /api/v1/jobs/{id} until completed → load result GLB into the
 *      Three.js canvas.
 *   2. User changes settings + clicks Regenerate → same flow with the current
 *      settings. Any in-flight poll is cancelled before kicking off a new one.
 *
 * Export integration (POST /api/v1/export + browser download) is Phase 7.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AppStateProvider, useAppState } from "@/state/AppState";
import { UploadForm } from "@/components/UploadForm";
import { SettingsPanel } from "@/components/SettingsPanel";
import { PreviewCanvas } from "@/components/PreviewCanvas";
import { DownloadPanel } from "@/components/DownloadPanel";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { pollJob, postExport, postPreview } from "@/api/client";
import type { ExportFormat } from "@/types/settings";

export function AppShell() {
  return (
    <AppStateProvider>
      <Layout />
    </AppStateProvider>
  );
}

function Layout() {
  const {
    gpx,
    settings,
    previewUrl,
    setPreviewUrl,
    jobStatus,
    setJobStatus,
    jobError,
    setJobError,
  } = useAppState();

  const pollAbortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight poll when the component unmounts.
  useEffect(() => () => pollAbortRef.current?.abort(), []);

  const generatePreview = useCallback(
    async (file: File) => {
      pollAbortRef.current?.abort();
      const controller = new AbortController();
      pollAbortRef.current = controller;

      setJobStatus("pending");
      setJobError(null);
      setPreviewUrl(null);

      try {
        const jobId = await postPreview(file, settings);
        if (controller.signal.aborted) return;
        const info = await pollJob(jobId, {
          intervalMs: 1000,
          signal: controller.signal,
          onUpdate: (i) => {
            if (!controller.signal.aborted) setJobStatus(i.status);
          },
        });
        if (controller.signal.aborted) return;
        if (info.status === "completed" && info.result_url) {
          setJobStatus("completed");
          setPreviewUrl(info.result_url);
        } else {
          setJobStatus("failed");
          setJobError(info.error ?? "unknown error");
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setJobStatus("failed");
        setJobError(err instanceof Error ? err.message : String(err));
      }
    },
    [settings, setJobStatus, setJobError, setPreviewUrl],
  );

  const handleUpload = useCallback(
    (file: File) => {
      void generatePreview(file);
    },
    [generatePreview],
  );

  const handleRegenerate = useCallback(() => {
    if (!gpx) return;
    void generatePreview(gpx);
  }, [gpx, generatePreview]);

  const [exporting, setExporting] = useState(false);

  const runExport = useCallback(
    async (fmt: ExportFormat) => {
      if (!gpx) return;
      pollAbortRef.current?.abort();
      const controller = new AbortController();
      pollAbortRef.current = controller;

      setExporting(true);
      setJobStatus("pending");
      setJobError(null);

      try {
        const jobId = await postExport(gpx, settings, fmt);
        if (controller.signal.aborted) return;
        const info = await pollJob(jobId, {
          intervalMs: 1000,
          signal: controller.signal,
          onUpdate: (i) => {
            if (!controller.signal.aborted) setJobStatus(i.status);
          },
        });
        if (controller.signal.aborted) return;
        if (info.status === "completed" && info.result_url) {
          setJobStatus("completed");
          triggerBrowserDownload(info.result_url, suggestedFilename(gpx.name, fmt));
        } else {
          setJobStatus("failed");
          setJobError(info.error ?? "unknown error");
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setJobStatus("failed");
        setJobError(err instanceof Error ? err.message : String(err));
      } finally {
        setExporting(false);
      }
    },
    [gpx, settings, setJobStatus, setJobError],
  );

  const handleExport = useCallback(
    (fmt: ExportFormat) => {
      void runExport(fmt);
    },
    [runExport],
  );

  const busy = exporting || jobStatus === "pending" || jobStatus === "processing";

  return (
    <div className="mx-auto flex min-h-screen max-w-[1400px] flex-col gap-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">TrailPrint3D</h1>
          <p className="text-sm text-[var(--color-ink-muted)]">
            Upload a GPX, preview, download a printable terrain model.
          </p>
        </div>
        <JobStatusBadge status={jobStatus} error={jobError} />
      </header>

      <UploadForm onUpload={handleUpload} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <PreviewCanvas url={previewUrl} />
        <div className="flex flex-col gap-4">
          <SettingsPanel onRegenerate={handleRegenerate} disabled={!gpx || busy} />
          <DownloadPanel onExport={handleExport} disabled={busy} />
        </div>
      </div>
    </div>
  );
}

/** Build a sensible download filename: <gpx-stem>.<format>. */
function suggestedFilename(gpxName: string, fmt: ExportFormat): string {
  const stem = gpxName.replace(/\.[gG][pP][xX]$/, "");
  return `${stem}.${fmt}`;
}

/** Trigger a same-origin file download with a chosen filename. */
function triggerBrowserDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
