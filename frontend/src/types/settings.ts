/**
 * Mirrors backend/app/models.py::GenerateSettings.
 * Locked in docs/phase2_pipeline_design.md.
 */

export type Shape = "square" | "circle" | "hexagon";
export type ExportFormat = "stl" | "obj" | "3mf" | "glb";
export type GenerateMode = "preview" | "export";

export interface GenerateSettings {
  shape: Shape;
  terrain_scale: number;
  track_thickness_mm: number;
  frame_thickness_mm: number;
  bbox_padding_percent: number;
  model_size_mm: number;
  min_base_thickness_mm: number;
  preview_subdivisions: number;
  export_subdivisions: number;
}

export const DEFAULT_SETTINGS: GenerateSettings = {
  shape: "hexagon",
  terrain_scale: 1.0,
  track_thickness_mm: 1.2,
  frame_thickness_mm: 5.0,
  bbox_padding_percent: 0.1,
  model_size_mm: 100.0,
  min_base_thickness_mm: 2.0,
  preview_subdivisions: 2,
  export_subdivisions: 4,
};

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  result_url: string | null;
  error: string | null;
}
