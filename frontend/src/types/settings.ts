/**
 * Mirrors backend/app/models.py::GenerateSettings.
 * Locked in docs/phase2_pipeline_design.md.
 */

export type Shape = "square" | "circle" | "hexagon";
export type HexagonOrientation = "flat_top" | "point_top";
export type BufferMode = "percent" | "absolute";
export type ExportFormat = "stl" | "obj" | "3mf" | "glb";
export type GenerateMode = "preview" | "export";

export interface GenerateSettings {
  shape: Shape;
  hexagon_orientation: HexagonOrientation;
  buffer_mode: BufferMode;
  buffer_percent: number;
  buffer_absolute_mm: number;
  buffer_min_mm: number;
  terrain_scale: number;
  track_thickness_mm: number;
  frame_thickness_mm: number;
  model_size_mm: number;
  min_base_thickness_mm: number;
  preview_subdivisions: number;
  export_subdivisions: number;
  bbox_padding_percent: number;
}

export const DEFAULT_SETTINGS: GenerateSettings = {
  shape: "hexagon",
  hexagon_orientation: "flat_top",
  buffer_mode: "percent",
  buffer_percent: 5.0,
  buffer_absolute_mm: 3.0,
  buffer_min_mm: 2.0,
  terrain_scale: 1.0,
  track_thickness_mm: 1.2,
  frame_thickness_mm: 5.0,
  model_size_mm: 100.0,
  min_base_thickness_mm: 2.0,
  preview_subdivisions: 2,
  export_subdivisions: 4,
  bbox_padding_percent: 0.1,
};

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  result_url: string | null;
  error: string | null;
}
