from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Shape(str, Enum):
    hexagon = "HEXAGON"
    square = "SQUARE"
    circle = "CIRCLE"


class ElevationApi(str, Enum):
    terrain_tiles = "TERRAIN-TILES"
    opentopodata = "OPENTOPODATA"
    open_elevation = "OPEN-ELEVATION"


class OpenTopoDataset(str, Enum):
    aster30m = "aster30m"
    srtm30m = "srtm30m"
    mapzen = "mapzen"
    ned10m = "ned10m"
    eudem25m = "eudem25m"
    nzdem8m = "nzdem8m"


class ElementMode(str, Enum):
    paint = "PAINT"
    single_color_remesh = "SINGLECOLORMODE_REMESH"
    separate = "SEPARATE"


class ExportFormat(str, Enum):
    stl = "stl"
    obj = "obj"
    three_mf = "3mf"


class JobState(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Generation settings — mirrors addon props.py, all fields optional.
# ---------------------------------------------------------------------------

class GenerationSettings(BaseModel):
    # Shape & size
    shape: Shape = Shape.hexagon
    obj_size: int = Field(default=100, ge=5, le=10000)
    rectangle_height: int = Field(default=100, ge=5, le=10000)
    shape_rotation: int = Field(default=0, ge=-360, le=360)

    # Terrain resolution & scale
    num_subdivisions: int = Field(default=4, ge=1, le=10)
    scale_elevation: float = Field(default=1.0, ge=0, le=10000)
    fixed_elevation_scale: bool = False
    min_thickness: float = Field(default=2.0, ge=0.5, le=1000)
    overwrite_path_elevation: bool = True
    x_terrain_offset: float = 0.0
    y_terrain_offset: float = 0.0

    # Track
    path_thickness: float = Field(default=1.2, ge=0.1, le=5.0)

    # Elevation API
    elevation_api: ElevationApi = ElevationApi.terrain_tiles
    opentopodata_dataset: OpenTopoDataset = OpenTopoDataset.aster30m

    # Water elements
    water_ponds: bool = False
    water_small_rivers: bool = False
    water_big_rivers: bool = False
    river_width: float = Field(default=1.0, ge=0.1, le=10.0)

    # Overlay elements
    forests: bool = False
    city_boundaries: bool = False
    greenspace: bool = False
    buildings: bool = False
    building_height_multiplier: float = Field(default=1.0, ge=0.01, le=10.0)

    # Roads
    roads_major: bool = False
    roads_medium: bool = False
    roads_minor: bool = False
    street_width_multiplier: float = Field(default=1.0, ge=0.1, le=10.0)

    # Print mode
    element_mode: ElementMode = ElementMode.paint
    single_color_mode: bool = False

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class JobAccepted(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: JobState
    progress: int = Field(ge=0, le=100)
    result_url: str | None = None
    error: str | None = None


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "error"]
    api: Literal["ok", "error"]
    redis: Literal["ok", "error"]
    celery: Literal["ok", "degraded", "error"]
