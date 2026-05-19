from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class GenerationSettings(BaseModel):
    # Shape & size
    shape: Literal["HEXAGON", "SQUARE", "CIRCLE", "OCTAGON", "ELLIPSE", "HEART"] = "HEXAGON"
    obj_size_mm: int = Field(100, ge=5, le=10000)
    shape_rotation: int = Field(0, ge=-360, le=360)
    rectangle_height: int = Field(100, ge=5, le=10000)
    ellipse_ratio: float = Field(0.75, gt=0.0, le=10.0)

    # Terrain
    elevation_scale: float = Field(1.0, ge=0)
    num_subdivisions: int = Field(4, ge=1, le=8)
    min_thickness: float = Field(2.0, ge=0.5)
    fixed_elevation_scale: bool = False
    plate_thickness: float = Field(5.0, ge=0)

    # Trail
    path_thickness: float = Field(1.2, ge=0.1, le=5)
    path_scale: float = Field(0.8, ge=0.01)
    overwrite_path_elevation: bool = True
    single_color_mode: bool = False

    # Elevation API
    api: Literal["TERRAIN-TILES", "OPENTOPODATA", "OPEN-ELEVATION", "OPENTOPOGRAPHY"] = "TERRAIN-TILES"
    # Dataset names: alphanumeric + hyphen/underscore, max 40 chars — prevents URL path injection
    dataset: str = Field("aster30m", pattern=r"^[a-zA-Z0-9_\-]{1,40}$")
    opentopography_dataset: str = Field("SRTMGL1", pattern=r"^[a-zA-Z0-9_\-]{1,40}$")

    # Scale mode
    scale_mode: Literal["FACTOR", "COORDINATES", "SCALE"] = "FACTOR"
    scale_lat1: float = Field(0.0, ge=-90.0, le=90.0)
    scale_lon1: float = Field(0.0, ge=-180.0, le=180.0)
    scale_lat2: float = Field(0.0, ge=-90.0, le=90.0)
    scale_lon2: float = Field(0.0, ge=-180.0, le=180.0)

    # OSM coloring layers
    water_ponds: bool = False
    water_small_rivers: bool = False
    water_big_rivers: bool = False
    include_forests: bool = False
    include_city: bool = False
    include_greenspace: bool = False
    include_farmland: bool = False
    include_glacier: bool = False

    # OSM elements
    include_buildings: bool = False
    roads_big: bool = False
    roads_med: bool = False
    roads_small: bool = False
    include_ocean: bool = False

    # Element mode
    element_mode: Literal["PAINT", "SINGLECOLORMODE_REMESH", "SEPARATE"] = "PAINT"

    # Text / frame — restrict to safe characters to prevent path traversal in Blender export
    trail_name: str = Field("", pattern=r"^[a-zA-Z0-9 _\-\.]{0,100}$")
    x_terrain_offset: float = 0.0
    y_terrain_offset: float = 0.0


class UploadResponse(BaseModel):
    file_id: str
    filename: str = Field(max_length=255)
    track_stats: "TrackStats"


class TrackStats(BaseModel):
    point_count: int
    length_km: float
    elevation_gain_m: float
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    date: Optional[str] = None


class PreviewRequest(BaseModel):
    file_id: str
    settings: GenerationSettings = Field(default_factory=GenerationSettings)


class TerrainPreviewStats(BaseModel):
    vertex_count: int
    face_count: int
    bbox: tuple[float, float, float, float]
    track_length_km: float


class PreviewResponse(BaseModel):
    glb_url: str
    terrain_stats: TerrainPreviewStats


class ExportRequest(BaseModel):
    file_id: str
    settings: GenerationSettings = Field(default_factory=GenerationSettings)
    format: Literal["STL", "OBJ", "3MF"] = "STL"


class ExportResponse(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "failed"]
    progress: int = 0
    message: str = ""
    error: str | None = None
    files: list[str] = Field(default_factory=list)
