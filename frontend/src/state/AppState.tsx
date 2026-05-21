/**
 * Context-based state for the Phase 5 frontend shell.
 *
 * Holds: the uploaded GPX (File), the current settings, the active preview URL,
 * the current job status. Phase 6 (preview integration) wires this to
 * POST /api/v1/preview; Phase 7 (export integration) adds the download flow.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DEFAULT_SETTINGS,
  type ExportFormat,
  type GenerateSettings,
  type JobStatus,
} from "@/types/settings";

interface AppState {
  gpx: File | null;
  setGpx: (f: File | null) => void;

  settings: GenerateSettings;
  setSetting: <K extends keyof GenerateSettings>(key: K, value: GenerateSettings[K]) => void;

  previewUrl: string | null;
  setPreviewUrl: (u: string | null) => void;

  jobStatus: JobStatus | null;
  setJobStatus: (s: JobStatus | null) => void;

  jobError: string | null;
  setJobError: (e: string | null) => void;

  exportFormat: ExportFormat;
  setExportFormat: (f: ExportFormat) => void;
}

const AppStateContext = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [gpx, setGpx] = useState<File | null>(null);
  const [settings, setSettings] = useState<GenerateSettings>(DEFAULT_SETTINGS);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("stl");

  const setSetting = useCallback(
    <K extends keyof GenerateSettings>(key: K, value: GenerateSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const value = useMemo<AppState>(
    () => ({
      gpx,
      setGpx,
      settings,
      setSetting,
      previewUrl,
      setPreviewUrl,
      jobStatus,
      setJobStatus,
      jobError,
      setJobError,
      exportFormat,
      setExportFormat,
    }),
    [gpx, settings, setSetting, previewUrl, jobStatus, jobError, exportFormat],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used inside an AppStateProvider");
  }
  return ctx;
}
