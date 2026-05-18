const API_BASE = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;
const POLL_TIMEOUT_MS = 5_000;

async function fetchWithTimeout(
  url: string,
  options: RequestInit & { signal?: AbortSignal; timeoutMs?: number } = {}
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: outerSignal, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // If the caller already has an AbortSignal, propagate it.
  // Handle the case where outerSignal is ALREADY aborted before this call.
  const abortHandler = () => controller.abort();
  if (outerSignal?.aborted) {
    controller.abort();
  } else {
    outerSignal?.addEventListener("abort", abortHandler, { once: true });
  }

  try {
    return await fetch(url, { ...rest, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    outerSignal?.removeEventListener("abort", abortHandler);
  }
}

function parseError(res: Response, fallback: string): string {
  // Always show the fallback message; statusText is unreliable under HTTP/2.
  return `HTTP ${res.status}: ${fallback}`;
}

export interface TrackStats {
  point_count: number;
  length_km: number;
  elevation_gain_m: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  date?: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  track_stats: TrackStats;
}

export interface GenerationSettings {
  shape?: "HEXAGON" | "SQUARE" | "CIRCLE" | "OCTAGON" | "ELLIPSE" | "HEART";
  obj_size_mm?: number;
  shape_rotation?: number;
  rectangle_height?: number;
  ellipse_ratio?: number;
  elevation_scale?: number;
  num_subdivisions?: number;
  min_thickness?: number;
  path_thickness?: number;
  path_scale?: number;
  overwrite_path_elevation?: boolean;
  api?: "TERRAIN-TILES" | "OPENTOPODATA" | "OPEN-ELEVATION" | "OPENTOPOGRAPHY";
  dataset?: string;
  water_ponds?: boolean;
  water_small_rivers?: boolean;
  water_big_rivers?: boolean;
  include_forests?: boolean;
  include_buildings?: boolean;
  roads_big?: boolean;
  roads_med?: boolean;
  roads_small?: boolean;
  element_mode?: "PAINT" | "SINGLECOLORMODE_REMESH" | "SEPARATE";
  plate_thickness?: number;
  trail_name?: string;
}

export interface PreviewResponse {
  glb_url: string;
  terrain_stats: Record<string, unknown>;
}

export interface ExportResponse {
  job_id: string;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  message: string;
  error?: string;
  files: string[];
}

export async function uploadFile(file: File, signal?: AbortSignal): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetchWithTimeout(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
    signal,
    timeoutMs: 60_000,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? parseError(res, "Upload failed"));
  }
  return res.json();
}

export async function generatePreview(
  fileId: string,
  settings: GenerationSettings,
  signal?: AbortSignal
): Promise<PreviewResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, settings }),
    signal,
    timeoutMs: 120_000,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? parseError(res, "Preview generation failed"));
  }
  return res.json();
}

export function resolvePreviewUrl(glbUrl: string): string {
  if (glbUrl.startsWith("http")) return glbUrl;
  return `${API_BASE}${glbUrl}`;
}

export async function startExport(
  fileId: string,
  settings: GenerationSettings,
  format: "STL" | "OBJ" | "3MF",
  signal?: AbortSignal
): Promise<ExportResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, settings, format }),
    signal,
    // 60 s: generous enough for a loaded queue to accept the task;
    // the actual generation runs in Celery and is polled separately.
    timeoutMs: 60_000,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? parseError(res, "Export failed"));
  }
  return res.json();
}

export class PollError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "PollError";
  }
}

export async function getJobStatus(jobId: string, signal?: AbortSignal): Promise<JobStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/api/job/${jobId}`, {
    signal,
    timeoutMs: POLL_TIMEOUT_MS,
  });
  if (!res.ok) throw new PollError(res.status, parseError(res, "Could not fetch job status"));
  return res.json();
}

export function downloadUrl(jobId: string, filename: string): string {
  return `${API_BASE}/api/download/${jobId}/${filename}`;
}
