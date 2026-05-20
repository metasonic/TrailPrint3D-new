/**
 * Frontend shell composition. Phase 5 wires the islands together with local
 * state but stubs the API calls — they become real fetch() calls in Phase 6/7.
 */

import { AppStateProvider, useAppState } from "@/state/AppState";
import { UploadForm } from "@/components/UploadForm";
import { SettingsPanel } from "@/components/SettingsPanel";
import { PreviewCanvas } from "@/components/PreviewCanvas";
import { DownloadPanel } from "@/components/DownloadPanel";
import { JobStatusBadge } from "@/components/JobStatusBadge";

export function AppShell() {
  return (
    <AppStateProvider>
      <Layout />
    </AppStateProvider>
  );
}

function Layout() {
  const { gpx, previewUrl, jobStatus, jobError } = useAppState();

  const handleUpload = (_file: File) => {
    // Phase 6 will POST /api/v1/preview here.
  };
  const handleRegenerate = () => {
    // Phase 6 will POST /api/v1/preview here.
  };
  const handleExport = (_fmt: string) => {
    // Phase 7 will POST /api/v1/export here.
  };

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
          <SettingsPanel onRegenerate={handleRegenerate} disabled={!gpx} />
          <DownloadPanel onExport={handleExport} />
        </div>
      </div>
    </div>
  );
}
