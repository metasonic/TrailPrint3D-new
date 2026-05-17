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
  downloadUrl,
  resolvePreviewUrl,
  type GenerationSettings,
  type TrackStats,
  type JobStatus,
} from "../lib/api";

const DEFAULT_SETTINGS: GenerationSettings = {
  shape: "HEXAGON",
  obj_size_mm: 100,
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
};

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
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [exportFormat, setExportFormat] = useState<"STL" | "OBJ" | "3MF">("STL");

  // Debounce slider-driven settings to avoid firing an API call on every tick
  const debouncedSettings = useDebounce(settings, 500);

  const previewAbortRef = useRef<AbortController | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handlePreview = useCallback(async (fid: string, s: GenerationSettings) => {
    // Cancel any in-flight preview request
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
      setPreviewError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      if (!controller.signal.aborted) setPreviewLoading(false);
    }
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setUploadError(null);
    setPreviewError(null);
    setGlbUrl(null);
    setJobStatus(null);
    try {
      const res = await uploadFile(file);
      setFileId(res.file_id);
      setTrackStats(res.track_stats);
      await handlePreview(res.file_id, settings);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    }
  }, [settings, handlePreview]);

  const handleRegenerate = () => {
    if (fileId) handlePreview(fileId, settings);
  };

  const updateSetting = <K extends keyof GenerationSettings>(
    key: K,
    value: GenerationSettings[K]
  ) => setSettings((s) => ({ ...s, [key]: value }));

  const clearPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleExport = async (fmt: "STL" | "OBJ" | "3MF") => {
    if (!fileId) return;
    clearPoll();
    setJobStatus({ job_id: "", status: "pending", progress: 0, message: "Starting…", files: [] });
    try {
      const { job_id } = await startExport(fileId, settings, fmt);
      setJobStatus((s) => (s ? { ...s, job_id } : null));

      // Single interval stored in ref — no accumulation across clicks
      pollRef.current = setInterval(async () => {
        try {
          const status = await getJobStatus(job_id);
          setJobStatus(status);
          if (status.status === "done" || status.status === "failed") {
            clearPoll();
          }
        } catch {
          // network hiccup — keep polling
        }
      }, 2000);
    } catch (e: unknown) {
      setJobStatus({
        job_id: "",
        status: "failed",
        progress: 0,
        message: "",
        error: e instanceof Error ? e.message : "Export failed",
        files: [],
      });
    }
  };

  // Clean up on unmount
  useEffect(() => () => { clearPoll(); previewAbortRef.current?.abort(); }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  return (
    <div className="app-grid">
      {/* ── Left panel ── */}
      <aside className="sidebar">
        {/* Upload zone */}
        <section
          className={`upload-zone${isDragging ? " dragging" : ""}${fileId ? " has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => document.getElementById("file-input")?.click()}
          role="button"
          tabIndex={0}
          aria-label="Drop a GPX or IGC file here, or click to browse"
          onKeyDown={(e) => e.key === "Enter" && document.getElementById("file-input")?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".gpx,.igc"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          {fileId && trackStats ? (
            <div className="upload-stats">
              <strong>✓ Track loaded</strong>
              <span>{trackStats.length_km.toFixed(1)} km · +{trackStats.elevation_gain_m.toFixed(0)} m</span>
              {trackStats.date && <span>{trackStats.date}</span>}
              <span className="muted">{trackStats.point_count.toLocaleString()} points</span>
            </div>
          ) : (
            <>
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
              <summary>Shape &amp; Size</summary>
              <label>Shape
                <select
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
              <label>Size (mm)
                <input type="number" min={5} max={10000} value={settings.obj_size_mm}
                  onChange={(e) => updateSetting("obj_size_mm", +e.target.value)} />
              </label>
              <label>Rotation (°)
                <input type="range" min={-180} max={180} value={settings.shape_rotation ?? 0}
                  onChange={(e) => updateSetting("shape_rotation", +e.target.value)} />
                <span>{settings.shape_rotation ?? 0}°</span>
              </label>
            </details>

            <details open className="settings-group">
              <summary>Terrain</summary>
              <label>Elevation Scale
                <input type="number" min={0} max={100} step={0.1} value={settings.elevation_scale}
                  onChange={(e) => updateSetting("elevation_scale", +e.target.value)} />
              </label>
              <label>Resolution (1–8)
                <input type="range" min={1} max={8} value={settings.num_subdivisions}
                  onChange={(e) => updateSetting("num_subdivisions", +e.target.value)} />
                <span>{settings.num_subdivisions}</span>
              </label>
              <label>Min Thickness (mm)
                <input type="number" min={0.5} max={50} step={0.5} value={settings.min_thickness}
                  onChange={(e) => updateSetting("min_thickness", +e.target.value)} />
              </label>
            </details>

            <details className="settings-group">
              <summary>Trail</summary>
              <label>Path Thickness (mm)
                <input type="number" min={0.1} max={5} step={0.1} value={settings.path_thickness}
                  onChange={(e) => updateSetting("path_thickness", +e.target.value)} />
              </label>
            </details>

            <details className="settings-group">
              <summary>Elevation API</summary>
              <label>Source
                <select
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

            <button className="btn-primary" onClick={handleRegenerate} disabled={previewLoading}>
              {previewLoading ? "Generating…" : "↻ Regenerate Preview"}
            </button>
            {previewError && (
              <div className="error-box" role="alert" aria-live="assertive">{previewError}</div>
            )}
          </>
        )}
      </aside>

      {/* ── Preview ── */}
      <main className="preview-area">
        <Preview3D
          glbUrl={glbUrl}
          loading={previewLoading}
          onError={(msg) => setPreviewError(msg)}
        />
      </main>

      {/* ── Download panel ── */}
      {fileId && (
        <footer className="download-panel">
          <div className="export-buttons">
            <span>Export as:</span>
            {(["STL", "OBJ", "3MF"] as const).map((fmt) => (
              <button
                key={fmt}
                className={`btn-export${exportFormat === fmt ? " active" : ""}`}
                onClick={() => { setExportFormat(fmt); handleExport(fmt); }}
                disabled={jobStatus?.status === "running" || jobStatus?.status === "pending"}
                aria-pressed={exportFormat === fmt}
              >
                {fmt}
              </button>
            ))}
          </div>

          {jobStatus && (
            <div className="job-status" role="status" aria-live="polite">
              <div className="progress-bar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={jobStatus.progress} role="progressbar">
                <div
                  className={`progress-fill ${jobStatus.status}`}
                  style={{ width: `${jobStatus.progress}%` }}
                />
              </div>
              <span className="progress-label">
                {jobStatus.status === "done"
                  ? "✓ Ready to download"
                  : jobStatus.status === "failed"
                  ? `✗ ${jobStatus.error ?? "Export failed"}`
                  : `${jobStatus.message || jobStatus.status} — ${jobStatus.progress}%`}
              </span>
              {jobStatus.status === "done" &&
                jobStatus.files.map((f) => (
                  <a
                    key={f}
                    href={downloadUrl(jobStatus.job_id, f)}
                    download={f}
                    className="btn-download"
                  >
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
