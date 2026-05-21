"""Pydantic models for the API and the pipeline.

`GenerateSettings` is the single source of truth for pipeline inputs and is
imported by `pipeline.generate`. Keeping it here (rather than in the pipeline
package) lets the FastAPI layer reuse the same validation that the worker
receives, with no duplication.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Shape = Literal["square", "circle", "hexagon"]
HexagonOrientation = Literal["flat_top", "point_top"]
BufferMode = Literal["percent", "absolute"]
ExportFormat = Literal["stl", "obj", "3mf", "glb"]
GenerateMode = Literal["preview", "export"]


class GenerateSettings(BaseModel):
    """Settings for one generate() invocation. Locked in docs/phase2_pipeline_design.md
    and refined for the geometric layout rules (see MEMORY.md "Phase 8 follow-up")."""

    shape: Shape = "hexagon"
    hexagon_orientation: HexagonOrientation = "flat_top"

    # Buffer between the track's 2D bbox and the terrain edge.
    # In `percent` mode, the buffer is `model_size_mm * buffer_percent/100`, then
    # clamped up to `buffer_min_mm` so small tracks still have a printable border.
    # In `absolute` mode, the buffer is exactly `buffer_absolute_mm`.
    buffer_mode: BufferMode = "percent"
    buffer_percent: float = Field(5.0, ge=0.0, le=100.0)
    buffer_absolute_mm: float = Field(3.0, gt=0.0, le=100.0)
    buffer_min_mm: float = Field(2.0, ge=0.0, le=100.0)

    terrain_scale: float = Field(1.0, gt=0.0, le=20.0)
    track_thickness_mm: float = Field(1.2, gt=0.0, le=20.0)
    frame_thickness_mm: float = Field(5.0, gt=0.0, le=50.0)

    # Internal pipeline defaults (not exposed in Phase 1 UI).
    model_size_mm: float = Field(100.0, gt=0.0, le=500.0)
    min_base_thickness_mm: float = Field(2.0, gt=0.0, le=20.0)
    preview_subdivisions: int = Field(2, ge=1, le=4)
    export_subdivisions: int = Field(4, ge=1, le=8)

    # DEM download safety margin (fraction of the shape extent). Internal.
    bbox_padding_percent: float = Field(0.1, ge=0.0, le=1.0)


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class JobEnqueueResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    result_url: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: bool
    celery: bool


class GenerateResult(BaseModel):
    """Returned by pipeline.generate.generate() and stored as the Celery task result."""

    output_filename: str
    mode: GenerateMode
    format: ExportFormat
    duration_seconds: float
    cache_hit: bool
    track_length_m: float
    elevation_gain_m: float
    bbox: tuple[float, float, float, float]
