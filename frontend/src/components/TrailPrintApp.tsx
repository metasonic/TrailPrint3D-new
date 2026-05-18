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

  // Debounce settings so slider drags don't fire a request on every tick
  const debouncedSettings = useDebounce(settings, 500);

  const previewAbortRef = useRef<AbortController | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Generation counter prevents orphaned intervals from a rapid double-click
  const exportGenRef = useRef(0);
  // Track which fileId has already had its initial preview triggered
  const lastPreviewedFileIdRef = useRef<string | null>(null);
  // React ref for the hidden file input (avoids getElementById)
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      if (e instanceof Error && e.name === "AbortError") return;
      if (!controller.signal.aborted) {
        setPreviewError(e instanceof Error ? e.message : "Preview failed");
      }
    } finally {
      if (!controller.signal.aborted) setPreviewLoading(false);
    }
  }, []);

  // Auto-regenerate preview when debounced settings change — but skip the
  // first trigger right after a new file is uploaded (handleFile already runs it).
  useEffect(() => {
    if (!fileId) return;
    if (fileId !== lastPreviewedFileIdRef.current) {
      // New file — handleFile triggered the initial preview; just record it
      lastPreviewedFileIdRef.current = fileId;
      return;
    }
    handlePreview(fileId, debouncedSettings);
  // handlePreview is stable (useCallback []); include it for exhaustive-deps correctness
  }, [debouncedSettings, fileId, handlePreview]);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const _startPolling = useCallback((job_id: string, gen: number) => {
    let pollAttempts = 0;
    pollRef.current = setInterval(async () => {
      if (gen !== exportGenRef.current) {
        clearInterval(pollRef.current ?? undefined);
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
          if (e.status === 404) {
            clearPoll();
            sessionStorage.removeItem(SESSION_KEY);
            setJobStatus((s) => s ? { ...s, status: "failed", error: "Export job expired — please re-export" } : null);
          } else if (e.status === 503) {
            setJobStatus((s) => s && s.status !== "done" && s.status !== "failed"
              ? { ...s, message: "Server busy, retrying…" } : s);
          }
        }
      }
    }, 2000);
  }, [clearPoll]);

  const handleFile = useCallback(async (file: File) => {
    // Cancel any in-flight export poll before starting fresh
    clearPoll();
    setUploadError(null);
    setPreviewError(null);
    setGlbUrl(null);
    setJobStatus(null);
    setFileId(null);
    // Reset loading immediately — if a previous request was aborted its finally
    // block won't fire setPreviewLoading(false), so we must reset it here.
    setPreviewLoading(false);
    previewAbortRef.current?.abort();
    setUploadLoading(true);
    try {
      const res = await uploadFile(file);
      setFileId(res.file_id);
      setTrackStats(res.track_stats);
      // Trigger initial preview immediately (before debouncedSettings catches up)
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

    // Increment generation counter — any interval from a previous click will
    // see the mismatch and self-terminate rather than clearing the new interval.
    const gen = ++exportGenRef.current;

    setJobStatus({ job_id: "", status: "pending", progress: 0, message: "Starting…", files: [] });
    try {
      const { job_id } = await startExport(fileId, settings, fmt);

      // Bail if a newer export click superseded this one while awaiting
      if (gen !== exportGenRef.current) return;

      setJobStatus((s) => (s ? { ...s, job_id } : null));
      // Persist job for recovery after page refresh
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

  // Resume polling if user refreshed during an export
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

  // Cleanup on unmount
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
      setUploadError("Only .gpx and .igc files are accepted");
      return;
    }
    handleFile(f);
  };

  const isExporting = jobStatus?.status === "running" || jobStatus?.status === "pending";

  return (
    <div className="app-grid">
      {/* ── Left panel ── */}
      <aside className="sidebar">
        <header className="app-header">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ color: "#60a5fa" }}>
            <path d="M3 17l4-8 4 4 3-6 4 8" />
            <rect x="2" y="19" width="20" height="2" rx="1" fill="currentColor" stroke="none" />
          </svg>
          <h1>TrailPrint3D</h1>
          <span>GPX → 3D Print</span>
        </header>

        {/* Upload zone */}
        <section
          className={`upload-zone${isDragging ? " dragging" : ""}${fileId ? " has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false); }}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Drop a GPX or IGC file here, or press Enter or Space to browse"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <input
            ref={fileInputRef}
            id="file-input"
            type="file"
            accept=".gpx,.igc"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {uploadLoading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <p>Uploading…</p>
            </>
          ) : fileId && trackStats ? (
            <div className="upload-stats">
              <strong>✓ Track loaded</strong>
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
        </section>
        {uploadError && (
          <div className="error-box" role="alert" aria-live="assertive">{uploadError}</div>
        )}

        {/* Settings */}
        {fileId && (
          <>
            <details open className="settings-group">
              <summary>Trail Name</summary>
              <label htmlFor="trail-name">
                Name
                <input
                  id="trail-name"
                  type="text"
                  maxLength={100}
                  placeholder="e.g. Mont Blanc Tour"
                  inputMode="text"
                  autoComplete="off"
                  value={settings.trail_name ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    // Silently strip characters the backend pattern rejects
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
                <input id="size-mm" type="number" min={5} max={10000} value={settings.obj_size_mm}
                  onChange={(e) => updateSetting("obj_size_mm", +e.target.value)} />
              </label>
              {settings.shape === "SQUARE" && (
                <label htmlFor="rect-height">Rectangle Height (mm)
                  <input id="rect-height" type="number" min={5} max={10000} value={settings.rectangle_height ?? 100}
                    onChange={(e) => updateSetting("rectangle_height", +e.target.value)} />
                </label>
              )}
              {settings.shape === "ELLIPSE" && (
                <label htmlFor="ellipse-ratio">Ellipse Ratio (0.1–3)
                  <input id="ellipse-ratio" type="number" min={0.1} max={3} step={0.05} value={settings.ellipse_ratio ?? 0.75}
                    onChange={(e) => updateSetting("ellipse_ratio", +e.target.value)} />
                </label>
              )}
              <label htmlFor="rotation-range">Rotation (°)
                <input id="rotation-range" type="range" min={-180} max={180} value={settings.shape_rotation ?? 0}
                  onChange={(e) => updateSetting("shape_rotation", +e.target.value || 0)} />
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{settings.shape_rotation ?? 0}°</span>
              </label>
            </details>

            <details open className="settings-group">
              <summary>Terrain</summary>
              <label htmlFor="elev-scale">Elevation Scale
                <input id="elev-scale" type="number" min={0} max={100} step={0.1} value={settings.elevation_scale}
                  onChange={(e) => updateSetting("elevation_scale", +e.target.value)} />
              </label>
              <label htmlFor="resolution-range">Resolution (1–8)
                <input id="resolution-range" type="range" min={1} max={8} value={settings.num_subdivisions}
                  onChange={(e) => updateSetting("num_subdivisions", +e.target.value)} />
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{settings.num_subdivisions}</span>
              </label>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                {(settings.num_subdivisions ?? 4) > 4 ? "Resolution > 4 renders at full detail in export only." : "Higher resolution increases generation time."}
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
              <label><input type="checkbox" checked={settings.water_ponds}
                onChange={(e) => updateSetting("water_ponds", e.target.checked)} /> Ponds &amp; Lakes</label>
              <label><input type="checkbox" checked={settings.water_small_rivers}
                onChange={(e) => updateSetting("water_small_rivers", e.target.checked)} /> Small Rivers</label>
              <label><input type="checkbox" checked={settings.water_big_rivers}
                onChange={(e) => updateSetting("water_big_rivers", e.target.checked)} /> Big Rivers</label>
              <label><input type="checkbox" checked={settings.include_forests}
                onChange={(e) => updateSetting("include_forests", e.target.checked)} /> Forests</label>
              <label><input type="checkbox" checked={settings.include_buildings}
                onChange={(e) => updateSetting("include_buildings", e.target.checked)} /> Buildings</label>
              <label><input type="checkbox" checked={settings.roads_big}
                onChange={(e) => updateSetting("roads_big", e.target.checked)} /> Major Roads</label>
              <label><input type="checkbox" checked={settings.roads_med}
                onChange={(e) => updateSetting("roads_med", e.target.checked)} /> Secondary Roads</label>
            </details>

            <button type="button" className="btn-primary btn-generate" onClick={handleRegenerate} disabled={previewLoading}>
              {previewLoading ? "Generating…" : "↻ Regenerate Preview"}
            </button>
            {previewError && (
              <div className="error-box" role="alert" aria-live="assertive">{previewError}</div>
            )}
          </>
        )}
      </aside>

      {/* ── Preview ── */}
      <section className="preview-area" aria-label="3D terrain preview">
        <Preview3D
          glbUrl={glbUrl}
          loading={previewLoading || uploadLoading}
          onError={(msg) => setPreviewError(msg)}
        />
      </section>

      {/* ── Download panel ── */}
      {fileId && (
        <footer className="download-panel">
          <div className="export-buttons" role="group" aria-label="Export format and trigger">
            <span>Format:</span>
            {(["STL", "OBJ", "3MF"] as const).map((fmt) => (
              <button
                key={fmt}
                type="button"
                className={`btn-export${exportFormat === fmt ? " active" : ""}`}
                onClick={() => setExportFormat(fmt)}
                aria-pressed={exportFormat === fmt}
              >
                {fmt}
              </button>
            ))}
            <button
              type="button"
              className="btn-primary btn-generate-export"
              onClick={() => handleExport(exportFormat)}
              disabled={isExporting}
            >
              Generate {exportFormat}
            </button>
          </div>

          {jobStatus && (
            <div className="job-status" role="status" aria-live="polite" aria-atomic="true">
              <div
                className="progress-bar"
                role="progressbar"
                aria-label="Export progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={jobStatus.progress}
                aria-valuetext={
                  jobStatus.status === "done"
                    ? "Complete"
                    : jobStatus.status === "failed"
                    ? "Failed"
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
                  ? "✓ Ready to download"
                  : jobStatus.status === "failed"
                  ? `✗ ${jobStatus.error ?? "Export failed"}`
                  : `${jobStatus.message || jobStatus.status} — ${jobStatus.progress}%`}
              </span>
              {jobStatus.status === "failed" && (
                <button type="button" className="btn-export" onClick={() => handleExport(exportFormat)}>
                  ↺ Retry
                </button>
              )}
              {jobStatus.status === "done" &&
                jobStatus.files.map((f) => (
                  <a key={f} href={downloadUrl(jobStatus.job_id, f)} download={f} className="btn-download">
                    ↓ {f}
                  </a>
                ))}
            </div>
          )}
        </footer>
      )}
    </div>
  );
}
