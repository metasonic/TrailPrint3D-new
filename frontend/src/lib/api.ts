const API_BASE = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

export interface TrackStats {
  point_count: number;
  length_km: number;
  elevation_gain_m: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  date: string;
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

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Upload failed");
  }
  return res.json();
}

export async function generatePreview(
  fileId: string,
  settings: GenerationSettings
): Promise<PreviewResponse> {
  const res = await fetch(`${API_BASE}/api/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, settings }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Preview generation failed");
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
  format: "STL" | "OBJ" | "3MF"
): Promise<ExportResponse> {
  const res = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, settings, format }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Export failed");
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/job/${jobId}`);
  if (!res.ok) throw new Error("Could not fetch job status");
  return res.json();
}

export function downloadUrl(jobId: string, filename: string): string {
  return `${API_BASE}/api/download/${jobId}/${filename}`;
}
