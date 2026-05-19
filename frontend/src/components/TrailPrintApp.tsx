/**
 * Main React island — owns all state: upload → preview → export.
 * Rendered client:load on the index page.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import Preview3D from "./Preview3D";
import {
  uploadFile,
  generatePreview,
  startExport,
  getJobStatus,
  PollError,
  downloadUrl,
  resolvePreviewUrl,
  type GenerationSettings,
  type TrackStats,
  type JobStatus,
} from "../lib/api";

const DEFAULT_SETTINGS: GenerationSettings = {
  shape: "HEXAGON",
  obj_size_mm: 100,
  shape_rotation: 0,
  rectangle_height: 100,
  ellipse_ratio: 0.75,
  elevation_scale: 1.0,
  num_subdivisions: 4,
  min_thickness: 2.0,
  path_thickness: 1.2,
  path_scale: 0.8,
  overwrite_path_elevation: true,
  api: "TERRAIN-TILES",
  element_mode: "PAINT",
  plate_thickness: 5.0,
  water_ponds: false,
  water_small_rivers: false,
  water_big_rivers: false,
  include_forests: false,
  include_buildings: false,
  roads_big: false,
  roads_med: false,
  roads_small: false,
  trail_name: "",
};

const MAX_POLL_ATTEMPTS = 300; // 10 minutes at 2 s interval
const SESSION_KEY = "tp3d_job";
const EXPORT_FORMATS = ["STL", "OBJ", "3MF"] as const;

function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export default function TrailPrintApp() {
  const [fileId, setFileId] = useState<string | null>(null);
  const [trackStats, setTrackStats] = useState<TrackStats | null>(null);
  const [settings, setSettings] = useState<GenerationSettings>(DEFAULT_SETTINGS);
  const [glbUrl, setGlbUrl] = useState<string | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [exportFormat, setExportFormat] = useState<"STL" | "OBJ" | "3MF">("STL");

  const debouncedSettings = useDebounce(settings, 500);

  const previewAbortRef = useRef<AbortController | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const exportGenRef = useRef(0);
  const lastPreviewedFileIdRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Focus target after file upload: first summary in settings (naturally focusable, no tabIndex needed)
  const firstSummaryRef = useRef<HTMLElement>(null);

  const handlePreview = useCallback(async (fid: string, s: GenerationSettings) => {
    previewAbortRef.current?.abort();
    const controller = new AbortController();
    previewAbortRef.current = controller;

    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await generatePreview(fid, s, controller.signal);
      if (!controller.signal.aborted) {
        setGlbUrl(resolvePreviewUrl(res.glb_url));
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") {
        // Only suppress silently if the user explicitly aborted (new upload / regen click).
        // If our own fetch timeout fired, controller.signal is still un-aborted → show message.
        if (!controller.signal.aborted) {
          setPreviewError("Preview timed out — try a smaller area or lower resolution");
        }
        return;
      }
      if (!controller.signal.aborted) {
        setPreviewError(e instanceof Error ? e.message : "Preview failed");
      }
    } finally {
      if (!controller.signal.aborted) setPreviewLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!fileId) return;
    if (fileId !== lastPreviewedFileIdRef.current) {
      lastPreviewedFileIdRef.current = fileId;
      return;
    }
    handlePreview(fileId, debouncedSettings);
  }, [debouncedSettings, fileId, handlePreview]);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const _startPolling = useCallback((job_id: string, gen: number) => {
    let pollAttempts = 0;
    let consecutiveNetworkErrors = 0;
    const id = setInterval(async () => {
      if (gen !== exportGenRef.current) {
        clearInterval(id);
        if (pollRef.current === id) pollRef.current = null;
        return;
      }
      pollAttempts++;
      if (pollAttempts > MAX_POLL_ATTEMPTS) {
        clearPoll();
        sessionStorage.removeItem(SESSION_KEY);
        setJobStatus((s) => s ? { ...s, status: "failed", error: "Export timed out" } : null);
        return;
      }
      try {
        const status = await getJobStatus(job_id);
        consecutiveNetworkErrors = 0;
        setJobStatus(status);
        if (status.status === "done" || status.status === "failed") {
          clearPoll();
          sessionStorage.removeItem(SESSION_KEY);
        }
      } catch (e: unknown) {
        if (e instanceof SyntaxError) {
          clearPoll();
          sessionStorage.removeItem(SESSION_KEY);
          setJobStatus((s) => s ? { ...s, status: "failed", error: "Invalid server response" } : null);
        } else if (e instanceof PollError) {
          consecutiveNetworkErrors = 0;
          if (e.status === 404) {
            clearPoll();
            sessionStorage.removeItem(SESSION_KEY);
            setJobStatus((s) => s ? { ...s, status: "failed", error: "Export job expired — please re-export" } : null);
          } else if (e.status === 503) {
            setJobStatus((s) => s && s.status !== "done" && s.status !== "failed"
              ? { ...s, message: "Server busy, retrying…" } : s);
          }
        } else {
          // Network failure (offline, DNS, etc.) — show message after 3 consecutive failures
          consecutiveNetworkErrors++;
          if (consecutiveNetworkErrors >= 3) {
            setJobStatus((s) => s ? { ...s, message: "Connection lost — retrying…" } : s);
          }
        }
      }
    }, 2000);
    pollRef.current = id;
  }, [clearPoll]);

  const handleFile = useCallback(async (file: File) => {
    clearPoll();
    setUploadError(null);
    setPreviewError(null);
    setGlbUrl(null);
    setJobStatus(null);
    setFileId(null);
    setPreviewLoading(false);
    previewAbortRef.current?.abort();
    setUploadLoading(true);
    try {
      const res = await uploadFile(file);
      setFileId(res.file_id);
      setTrackStats(res.track_stats);
      // Shift keyboard focus to the first settings summary after controls appear
      setTimeout(() => firstSummaryRef.current?.focus(), 80);
      await handlePreview(res.file_id, settings);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploadLoading(false);
    }
  }, [settings, handlePreview, clearPoll]);

  const handleRegenerate = useCallback(() => {
    if (fileId) handlePreview(fileId, settings);
  }, [fileId, settings, handlePreview]);

  const updateSetting = <K extends keyof GenerationSettings>(
    key: K,
    value: GenerationSettings[K]
  ) => setSettings((s) => ({ ...s, [key]: value }));

  const handleExport = useCallback(async (fmt: "STL" | "OBJ" | "3MF") => {
    if (!fileId) return;
    clearPoll();
    const gen = ++exportGenRef.current;
    setJobStatus({ job_id: "", status: "pending", progress: 0, message: "Starting…", files: [] });
    try {
      const { job_id } = await startExport(fileId, settings, fmt);
      if (gen !== exportGenRef.current) return;
      setJobStatus((s) => (s ? { ...s, job_id } : null));
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ job_id, format: fmt }));
      _startPolling(job_id, gen);
    } catch (e: unknown) {
      if (gen !== exportGenRef.current) return;
      setJobStatus({
        job_id: "",
        status: "failed",
        progress: 0,
        message: "",
        error: e instanceof Error ? e.message : "Export failed",
        files: [],
      });
    }
  }, [fileId, settings, clearPoll, _startPolling]);

  // Resume polling after page refresh
  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (!saved) return;
    try {
      const { job_id, format } = JSON.parse(saved) as { job_id: string; format: "STL" | "OBJ" | "3MF" };
      setExportFormat(format);
      setJobStatus({ job_id, status: "pending", progress: 0, message: "Resuming export…", files: [] });
      const gen = ++exportGenRef.current;
      _startPolling(job_id, gen);
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => {
    clearPoll();
    previewAbortRef.current?.abort();
  }, [clearPoll]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (!f) return;
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (ext !== "gpx" && ext !== "igc") {
      setUploadError(`Only .gpx and .igc files are accepted. You selected: ${f.name}`);
      return;
    }
    handleFile(f);
  };

  const isExporting = jobStatus?.status === "running" || jobStatus?.status === "pending";

  // Roving tabIndex + arrow-key navigation for the export format radio group
  const handleFormatKeyDown = (e: React.KeyboardEvent, fmt: typeof EXPORT_FORMATS[number]) => {
    const idx = EXPORT_FORMATS.indexOf(fmt);
    let next: typeof EXPORT_FORMATS[number] | undefined;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      next = EXPORT_FORMATS[(idx + 1) % EXPORT_FORMATS.length];
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      next = EXPORT_FORMATS[(idx - 1 + EXPORT_FORMATS.length) % EXPORT_FORMATS.length];
    }
    if (next) {
      setExportFormat(next);
      document.getElementById(`fmt-${next}`)?.focus();
    }
  };

  return (
    <div className="app-grid">
      {/* ── Left panel ── */}
      <aside className="sidebar">
        <header className="app-header">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true" style={{ color: "#60a5fa" }}>
            <path d="M3 17l4-8 4 4 3-6 4 8" />
            <rect x="2" y="18" width="20" height="2.5" rx="1" fill="currentColor" stroke="none" />
          </svg>
          <h1>TrailPrint3D</h1>
          <span>GPX ▸ 3D Print</span>
        </header>

        {/* Upload zone — <label> wrapping a visually-hidden input gives native
            file-dialog activation across all browsers and assistive technologies,
            without relying on scripted .click() on a display:none element. */}
        <label
          htmlFor="file-input"
          className={`upload-zone${isDragging ? " dragging" : ""}${fileId ? " has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false); }}
          onDrop={onDrop}
          aria-label="Drop a GPX or IGC file here, or press Enter to browse"
        >
          <input
            ref={fileInputRef}
            id="file-input"
            type="file"
            accept=".gpx,.igc"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const ext = f.name.split(".").pop()?.toLowerCase();
              if (ext !== "gpx" && ext !== "igc") {
                setUploadError(`Only .gpx and .igc files are accepted. You selected: ${f.name}`);
                return;
              }
              handleFile(f);
            }}
          />
          {uploadLoading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <p>Uploading…</p>
            </>
          ) : fileId && trackStats ? (
            <div className="upload-stats">
              <strong><span aria-hidden="true">✓ </span>Track loaded</strong>
              <span>{trackStats.length_km.toFixed(1)} km · +{trackStats.elevation_gain_m.toFixed(0)} m</span>
              {trackStats.date && <span>{trackStats.date}</span>}
              <span className="muted">{trackStats.point_count.toLocaleString()} points</span>
            </div>
          ) : (
            <>
              <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              <p>Drop a GPX / IGC file</p>
              <p className="muted">or click to browse</p>
            </>
          )}
        </label>
        {uploadError && (
          <div className="error-box" role="alert">{uploadError}</div>
        )}

        {/* Settings — only rendered once a file is loaded */}
        {fileId && (
          <>
            <details className="settings-group">
              <summary ref={firstSummaryRef}>Trail Name</summary>
              <label htmlFor="trail-name">
                Name
                <input
                  id="trail-name"
                  type="text"
                  maxLength={100}
                  placeholder="e.g. Mont Blanc Tour"
                  autoComplete="on"
                  value={settings.trail_name ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    updateSetting("trail_name", v.replace(/[^a-zA-Z0-9 _\-\.]/g, ""));
                  }}
                />
              </label>
            </details>

            <details open className="settings-group">
              <summary>Shape &amp; Size</summary>
              <label htmlFor="shape-select">Shape
                <select
                  id="shape-select"
                  value={settings.shape}
                  onChange={(e) => updateSetting("shape", e.target.value as GenerationSettings["shape"])}
                >
                  <option value="HEXAGON">Hexagon</option>
                  <option value="SQUARE">Rectangle</option>
                  <option value="CIRCLE">Circle</option>
                  <option value="OCTAGON">Octagon</option>
                  <option value="ELLIPSE">Ellipse</option>
                  <option value="HEART">Heart</option>
                </select>
              </label>
              <label htmlFor="size-mm">Size (mm)
                <input id="size-mm" type="number" min={5} max={10000} step={1} value={settings.obj_size_mm}
                  onChange={(e) => updateSetting("obj_size_mm", Math.max(5, Math.min(10000, +e.target.value || 100)))} />
              </label>
              {settings.shape === "SQUARE" && (
                <label htmlFor="rect-height">Rectangle Height (mm)
                  <input id="rect-height" type="number" min={5} max={10000} step={1} value={settings.rectangle_height ?? 100}
                    onChange={(e) => updateSetting("rectangle_height", Math.max(5, Math.min(10000, +e.target.value || 100)))} />
                </label>
              )}
              {settings.shape === "ELLIPSE" && (
                <label htmlFor="ellipse-ratio">Ellipse Ratio (0.1–3)
                  <input id="ellipse-ratio" type="number" min={0.1} max={3} step={0.05} value={settings.ellipse_ratio ?? 0.75}
                    onChange={(e) => updateSetting("ellipse_ratio", +e.target.value)} />
                </label>
              )}
              <label htmlFor="rotation-range">Rotation (°)
                <input
                  id="rotation-range"
                  type="range"
                  min={-180} max={180}
                  value={settings.shape_rotation ?? 0}
                  aria-valuetext={`${settings.shape_rotation ?? 0} degrees`}
                  onChange={(e) => updateSetting("shape_rotation", +e.target.value || 0)}
                />
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{settings.shape_rotation ?? 0}°</span>
              </label>
            </details>

            <details className="settings-group">
              <summary>Terrain</summary>
              <label htmlFor="elev-scale">Elevation Scale
                <input id="elev-scale" type="number" min={0.01} max={100} step={0.1} value={settings.elevation_scale}
                  onChange={(e) => updateSetting("elevation_scale", Math.max(0.01, +e.target.value))} />
              </label>
              <label htmlFor="resolution-range">Resolution (1–8)
                <input
                  id="resolution-range"
                  type="range"
                  min={1} max={8}
                  value={settings.num_subdivisions}
                  aria-valuetext={`${settings.num_subdivisions} subdivisions`}
                  onChange={(e) => updateSetting("num_subdivisions", +e.target.value)}
                />
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{settings.num_subdivisions}</span>
              </label>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                {(settings.num_subdivisions ?? 4) > 4 ? "Resolution > 4 uses full detail in export only." : "Higher values increase generation time."}
              </p>
              <label htmlFor="min-thick">Min Thickness (mm)
                <input id="min-thick" type="number" min={0.5} max={50} step={0.5} value={settings.min_thickness}
                  onChange={(e) => updateSetting("min_thickness", +e.target.value)} />
              </label>
            </details>

            <details className="settings-group">
              <summary>Trail</summary>
              <label htmlFor="path-thick">Path Thickness (mm)
                <input id="path-thick" type="number" min={0.1} max={5} step={0.1} value={settings.path_thickness}
                  onChange={(e) => updateSetting("path_thickness", +e.target.value)} />
              </label>
            </details>

            <details className="settings-group">
              <summary>Elevation API</summary>
              <label htmlFor="api-select">Source
                <select
                  id="api-select"
                  value={settings.api}
                  onChange={(e) => updateSetting("api", e.target.value as GenerationSettings["api"])}
                >
                  <option value="TERRAIN-TILES">Terrain Tiles (fastest)</option>
                  <option value="OPENTOPODATA">OpenTopoData</option>
                  <option value="OPEN-ELEVATION">Open-Elevation</option>
                  <option value="OPENTOPOGRAPHY">OpenTopography (API key required)</option>
                </select>
              </label>
            </details>

            <details className="settings-group">
              <summary>OSM Layers <span className="badge">+30–60s</span></summary>
              <label htmlFor="osm-ponds">
                <input id="osm-ponds" type="checkbox" checked={settings.water_ponds}
                  onChange={(e) => updateSetting("water_ponds", e.target.checked)} />
                Ponds &amp; Lakes
              </label>
              <label htmlFor="osm-small-rivers">
                <input id="osm-small-rivers" type="checkbox" checked={settings.water_small_rivers}
                  onChange={(e) => updateSetting("water_small_rivers", e.target.checked)} />
                Small Rivers
              </label>
              <label htmlFor="osm-big-rivers">
                <input id="osm-big-rivers" type="checkbox" checked={settings.water_big_rivers}
                  onChange={(e) => updateSetting("water_big_rivers", e.target.checked)} />
                Big Rivers
              </label>
              <label htmlFor="osm-forests">
                <input id="osm-forests" type="checkbox" checked={settings.include_forests}
                  onChange={(e) => updateSetting("include_forests", e.target.checked)} />
                Forests
              </label>
              <label htmlFor="osm-buildings">
                <input id="osm-buildings" type="checkbox" checked={settings.include_buildings}
                  onChange={(e) => updateSetting("include_buildings", e.target.checked)} />
                Buildings
              </label>
              <label htmlFor="osm-roads-big">
                <input id="osm-roads-big" type="checkbox" checked={settings.roads_big}
                  onChange={(e) => updateSetting("roads_big", e.target.checked)} />
                Major Roads
              </label>
              <label htmlFor="osm-roads-med">
                <input id="osm-roads-med" type="checkbox" checked={settings.roads_med}
                  onChange={(e) => updateSetting("roads_med", e.target.checked)} />
                Secondary Roads
              </label>
              <label htmlFor="osm-roads-small">
                <input id="osm-roads-small" type="checkbox" checked={settings.roads_small}
                  onChange={(e) => updateSetting("roads_small", e.target.checked)} />
                Small Roads
              </label>
            </details>

            {/* aria-disabled keeps the button in tab order so screen readers hear
                the "Generating…" label change; disabled would silently remove focus. */}
            <button
              type="button"
              className="btn-primary"
              onClick={previewLoading ? undefined : handleRegenerate}
              aria-disabled={previewLoading}
              style={previewLoading ? { opacity: 0.65, cursor: "not-allowed" } : undefined}
            >
              {previewLoading
                ? "Generating…"
                : <><span aria-hidden="true">↻ </span>Regenerate Preview</>}
            </button>
          </>
        )}
      </aside>

      {/* ── Preview ── */}
      <section className="preview-area" aria-label="3D terrain preview">
        <Preview3D
          glbUrl={glbUrl}
          loading={previewLoading || uploadLoading}
          loadingMessage={uploadLoading ? "Uploading file…" : "Generating preview…"}
          errorMessage={previewError}
          onError={(msg) => setPreviewError(msg)}
        />
      </section>

      {/* ── Download panel — visible when file loaded OR when a job exists after refresh ── */}
      {(fileId || jobStatus) && (
        <footer className="download-panel">
          {fileId && (
            <div className="export-buttons">
              {/* role="radiogroup" + role="radio" communicates mutual exclusivity to AT;
                  roving tabIndex + arrow-key handler provides standard radio keyboard UX. */}
              <div
                role="radiogroup"
                aria-label="Export format"
                style={{ display: "contents" }}
              >
                {EXPORT_FORMATS.map((fmt) => (
                  <button
                    key={fmt}
                    id={`fmt-${fmt}`}
                    type="button"
                    role="radio"
                    aria-checked={exportFormat === fmt}
                    className={`btn-export${exportFormat === fmt ? " active" : ""}`}
                    tabIndex={exportFormat === fmt ? 0 : -1}
                    onClick={() => setExportFormat(fmt)}
                    onKeyDown={(e) => handleFormatKeyDown(e, fmt)}
                  >
                    {fmt}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="btn-primary btn-generate-export"
                onClick={isExporting ? undefined : () => handleExport(exportFormat)}
                aria-disabled={isExporting}
                aria-busy={isExporting}
                style={isExporting ? { opacity: 0.65, cursor: "not-allowed" } : undefined}
              >
                {isExporting ? "Exporting…" : `Generate ${exportFormat}`}
              </button>
            </div>
          )}

          {jobStatus && (
            // aria-atomic="false" prevents the entire status block being re-read on every
            // 2-second poll update; individual child elements carry their own live semantics.
            <div className="job-status" role="status" aria-live="polite" aria-atomic="false">
              <div
                className="progress-bar"
                role="progressbar"
                aria-label="Export progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={jobStatus.progress}
                aria-valuetext={
                  jobStatus.status === "done" ? "Complete"
                  : jobStatus.status === "failed" ? "Failed"
                  : `${jobStatus.progress}%`
                }
              >
                <div
                  className={`progress-fill ${jobStatus.status}`}
                  style={{ width: `${jobStatus.progress}%` }}
                />
              </div>
              <span className={`progress-label${jobStatus.status === "failed" ? " progress-label--error" : ""}`}>
                {jobStatus.status === "done"
                  ? <><span aria-hidden="true">✓ </span>Ready to download</>
                  : jobStatus.status === "failed"
                  ? <><span aria-hidden="true">✗ </span>{jobStatus.error ?? "Export failed"}</>
                  : `${jobStatus.message || jobStatus.status} — ${jobStatus.progress}%`}
              </span>
              {jobStatus.status === "failed" && (
                <button type="button" className="btn-export" onClick={() => handleExport(exportFormat)}>
                  <span aria-hidden="true">↺ </span>Retry
                </button>
              )}
              {jobStatus.status === "done" &&
                jobStatus.files.map((f) => (
                  <a
                    key={f}
                    href={downloadUrl(jobStatus.job_id, f)}
                    download={f}
                    className="btn-download"
                    title={f}
                  >
                    <span aria-hidden="true">↓</span>{f}
                  </a>
                ))}
            </div>
          )}
        </footer>
      )}
    </div>
  );
}
