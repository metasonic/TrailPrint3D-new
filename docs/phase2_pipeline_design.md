# Phase 2 - Pipeline Design

This document locks the public surface of the `pipeline/` package and the
`GenerateSettings` schema for Phase 1 MVP. It supersedes any conflicting
recommendations in `docs/phase1_repo_analysis.md`.

No code is written in Phase 2. Phase 4 implements these signatures.

## Module layout

```
backend/
  app/
    main.py              FastAPI app, routes
    settings.py          Pydantic BaseSettings (env vars)
    models.py            Pydantic API models, GenerateSettings
    celery_app.py        Celery instance + config
    tasks.py             Celery tasks that call pipeline.generate
  pyproject.toml
pipeline/
  __init__.py            Re-exports the public surface
  terrain.py             DEM download + cache, projection, grid triangulation
  track.py               GPX parse, projection, Frenet-frame tube extrusion
  frame.py               Boundary polygon + extrusion (square/circle/hexagon)
  assembly.py            Boolean union via Manifold
  export.py              glTF/GLB, STL, OBJ, 3MF via trimesh.exchange.export
  generate.py            Orchestrator: gpx_path + settings + output_path + mode
```

No other modules in `pipeline/`. `GenerateSettings` lives in `backend/app/models.py`
and is imported by `pipeline.generate`, so the pipeline depends on `pydantic`
but not on FastAPI or Celery. This keeps the pipeline runnable from the CLI
for testing (Phase 4 acceptance criterion).

## Settings schema (GenerateSettings)

Defined in `backend/app/models.py`. The five fields the brief mandates as
user-facing are at the top; the rest are pipeline-internal defaults the API
exposes so callers can override them but the UI does not have to surface them
in Phase 1.

```python
from typing import Literal
from pydantic import BaseModel, Field

class GenerateSettings(BaseModel):
    # Brief's panel-exposed Phase 1 parameters
    shape: Literal["square", "circle", "hexagon"] = "hexagon"
    terrain_scale: float = Field(1.0, gt=0.0, le=20.0)
    track_thickness_mm: float = Field(1.2, gt=0.0, le=20.0)  # tube diameter
    frame_thickness_mm: float = Field(5.0, gt=0.0, le=50.0)  # vertical extrusion of frame
    bbox_padding_percent: float = Field(0.1, ge=0.0, le=1.0) # fraction of track extent

    # Pipeline internals with sensible defaults (not exposed in Phase 1 UI)
    model_size_mm: float = Field(100.0, gt=0.0, le=500.0)    # longest physical edge of frame
    min_base_thickness_mm: float = Field(2.0, gt=0.0, le=20.0) # printable base under lowest terrain
    preview_subdivisions: int = Field(2, ge=1, le=4)         # terrain grid downsample for preview
    export_subdivisions: int = Field(4, ge=1, le=8)          # terrain grid resolution for export
```

Validation, types, and bounds are enforced by Pydantic at API boundary.
Pipeline functions trust the schema and do not re-validate.

## generate.py - orchestrator contract

```python
from pathlib import Path
from typing import Literal
from backend.app.models import GenerateSettings

GenerateMode = Literal["preview", "export"]
ExportFormat = Literal["stl", "obj", "3mf", "glb"]

class GenerateResult(BaseModel):
    output_path: Path
    mode: GenerateMode
    format: ExportFormat
    duration_seconds: float
    cache_hit: bool            # True if DEM came from cache
    track_length_m: float
    elevation_gain_m: float
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat

def generate(
    gpx_path: Path,
    settings: GenerateSettings,
    output_path: Path,
    mode: GenerateMode,
    export_format: ExportFormat | None = None,  # required if mode == "export"
) -> GenerateResult:
    """
    Orchestrates the full pipeline.

    mode == "preview":  exports GLB at preview resolution. export_format ignored.
    mode == "export":   exports the requested format at full resolution.

    Raises:
      ValueError on bad inputs
      RuntimeError on DEM download failure, boolean union failure
    """
```

Internal flow (mode == "export" shown; "preview" skips full resolution and
forces GLB):

```
1. track = pipeline.track.load_track(gpx_path)
2. utm_crs = pipeline.track.pick_utm_crs(track)
3. projected_track = pipeline.track.project_to_utm(track, utm_crs)
4. bbox_wgs84 = pipeline.track.compute_bbox(track, padding=settings.bbox_padding_percent)
5. dem_array, dem_transform, cache_hit = pipeline.terrain.fetch_dem(bbox_wgs84)
6. terrain_mesh = pipeline.terrain.build_terrain_mesh(
       dem_array, dem_transform, utm_crs,
       subdivisions=settings.export_subdivisions (or preview_subdivisions),
       scale=settings.terrain_scale,
       base_thickness=settings.min_base_thickness_mm,
       model_size_mm=settings.model_size_mm,
   )
7. frame_mesh = pipeline.frame.build_frame(
       shape=settings.shape,
       terrain_mesh.bounds,
       thickness_mm=settings.frame_thickness_mm,
   )
8. track_mesh = pipeline.track.build_track_tube(
       projected_track, terrain_mesh,
       diameter_mm=settings.track_thickness_mm,
   )
9. assembled = pipeline.assembly.union([terrain_mesh, frame_mesh, track_mesh])
10. pipeline.export.export_mesh(assembled, output_path, fmt)
11. return GenerateResult(...)
```

## terrain.py - signatures

```python
from pathlib import Path
import numpy as np
import trimesh
from pyproj import CRS

BBoxWGS84 = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat

def fetch_dem(bbox: BBoxWGS84) -> tuple[np.ndarray, "Affine", bool]:
    """
    Downloads (or reads from cache) an SRTM 30 m GeoTIFF for the bbox.
    Returns (elevation_array, geotransform, cache_hit).
    Uses ELEVATION_CACHE_DIR. Cache key rounds bbox to 4 decimal degrees.
    """

def build_terrain_mesh(
    dem: np.ndarray,
    transform: "Affine",
    target_crs: CRS,
    subdivisions: int,
    scale: float,
    base_thickness: float,
    model_size_mm: float,
) -> trimesh.Trimesh:
    """
    Reprojects DEM samples into target_crs (UTM), builds a Delaunay
    triangulation of the grid, applies vertical scale, drops a flat base at
    (min_z - base_thickness) so the mesh is watertight and printable.
    Returns a Trimesh whose bounding box max-edge is model_size_mm.
    """
```

DEM cache: small private helper `_cache_path(bbox) -> Path` and
`_load_or_download(bbox) -> Path`. No public cache API in Phase 1.

## track.py - signatures

```python
from pathlib import Path
import numpy as np
import trimesh
from pyproj import CRS

class Track(BaseModel):
    points: list[tuple[float, float, float]]  # lon, lat, elevation_m
    name: str | None
    length_m: float
    elevation_gain_m: float

def load_track(gpx_path: Path) -> Track:
    """Parses a GPX file with gpxpy. Concatenates all tracks and segments."""

def pick_utm_crs(track: Track) -> CRS:
    """Picks the UTM zone for the track centroid."""

def project_to_utm(track: Track, target_crs: CRS) -> np.ndarray:
    """Returns Nx3 array of (easting, northing, elevation) in meters."""

def compute_bbox(track: Track, padding: float) -> BBoxWGS84:
    """track bbox in WGS84, expanded by `padding` fraction in each direction."""

def build_track_tube(
    projected_track: np.ndarray,
    terrain_mesh: trimesh.Trimesh,
    diameter_mm: float,
    segments: int = 12,
) -> trimesh.Trimesh:
    """
    Casts track points onto the terrain surface (ray-down) so the tube hugs
    the relief, then sweeps a circular cross-section along the path using a
    Frenet frame (tangent / normal / binormal). Returns a watertight tube.

    NOTE: diameter_mm is the OUTER diameter of the tube, after the same
    physical-size scaling that was applied to the terrain mesh.
    """
```

## frame.py - signatures

```python
import trimesh

def build_frame(
    shape: Literal["square", "circle", "hexagon"],
    terrain_bounds: np.ndarray,  # 2x3 trimesh bounds
    thickness_mm: float,
) -> trimesh.Trimesh:
    """
    Builds a 2D shapely polygon sized to wrap the terrain bounds (with a
    small inset so terrain and frame interlock in the union), then extrudes
    it vertically by thickness_mm. Returns a Trimesh.
    """
```

For circle and hexagon: radius = half of max(width, height) of terrain bounds.
For square: side = max(width, height).

## assembly.py - signatures

```python
import trimesh

def union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Boolean union of all input meshes using the Manifold engine via
    trimesh.boolean.union(meshes, engine="manifold").

    Raises RuntimeError if Manifold is unavailable or returns a non-manifold
    result (we do not silently fall back; failing loudly preserves print
    safety).
    """
```

## export.py - signatures

```python
from pathlib import Path
import trimesh

ExportFormat = Literal["stl", "obj", "3mf", "glb"]

def export_mesh(mesh: trimesh.Trimesh, path: Path, fmt: ExportFormat) -> None:
    """
    Dispatch to trimesh.exchange.export by format. Ensures parent dir exists.
    GLB used for both 'preview' mode output and final 'glb' downloads.
    """
```

## What is NOT in Phase 1 (re-affirmation)

The following appear in `docs/phase1_repo_analysis.md` but are deferred:

- Land-cover coloring (water, forest, scree, city, greenspace, farmland, glacier)
- Buildings and roads (Overpass)
- Contour lines
- Magnet holes, dovetails, engraving
- Text shapes (hexagon_inner_text etc.)
- Plate / backplate / bevel
- Single-color mode
- Mountain coloring by elevation threshold
- Preset save / load
- Multi-backend elevation API abstraction (we use the `elevation` package only)
- Web Mercator projection (we use local UTM)
- `pipeline/config.py`, `pipeline/cache.py`, `pipeline/elevation.py`,
  `pipeline/track_extrusion.py`, `pipeline/constants.py` (folded into the
  six modules above or into `backend/`)

## Risks carried into Phase 4

1. **Manifold availability** in the runtime image — if `manifold3d` is not
   importable, `assembly.union` will raise. Phase 4 must install it and
   verify in the test script.
2. **Frenet-frame stability** at sharp track turns. If the tangent reverses
   direction we get a twisted tube. Phase 4 must use the rotation-minimizing
   frame (parallel transport) and add a test on a synthetic switchback.
3. **DEM cache key collisions** — rounding bbox to 4 decimal degrees groups
   bboxes within ~11 m of each other. For Phase 1 this is acceptable since
   SRTM 30 m resolution exceeds that anyway, but it could merge two
   semantically different requests if the user uploads two near-identical
   GPX files. Will revisit if it bites.
