"""Orchestrator: GPX in, 3D printable mesh out. Pure Python, no Blender."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.app.models import ExportFormat, GenerateMode, GenerateResult, GenerateSettings
from pipeline import assembly, export, frame, terrain, track
from pipeline.layout import plan

logger = logging.getLogger(__name__)


def generate(
    gpx_path: Path,
    settings: GenerateSettings,
    output_path: Path,
    mode: GenerateMode,
    export_format: ExportFormat,
) -> GenerateResult:
    """Run the full pipeline.

    Spatial rules (single source of truth: pipeline/layout.py):
      1. Track bbox centroid lands at the model origin.
      2. Terrain extends past the track bbox by the configured buffer on all
         sides (percent of model_size_mm with a min clamp, or absolute mm).
      3. The base shape (square/circle/hexagon) circumscribes the buffered
         track bbox per the shape-specific rules in layout._shape_polygon.
      4. The clipped terrain, the visible base frame, and the boolean clip
         volume all extrude the *same* shapely polygon — no drift possible.
      5. Track points are cast onto the DEM surface (overwriting GPX
         elevations) so the tube hugs the relief.
    """
    t0 = time.perf_counter()

    # 1. Load and project the track.
    parsed = track.load_track(gpx_path)
    utm_crs = track.pick_utm_crs(parsed)
    projected = track.project_to_utm(parsed, utm_crs)

    # 2. Plan the whole geometry in one go.
    layout = plan(projected, utm_crs, settings)
    logger.info(
        "layout: scale=%.6f mm/m, buffer=%.2fmm, shape_extent=%.2fx%.2fmm, dem_bbox=%s",
        layout.scale,
        layout.buffer_mm,
        *layout.shape_extent_mm,
        layout.dem_bbox_wgs84,
    )

    # 3. Download DEM for the planned bbox.
    dem_array, dem_transform, dem_crs, cache_hit = terrain.fetch_dem(layout.dem_bbox_wgs84)

    # 4. Build the terrain mesh (centred on track centroid, scaled to mm).
    subdivisions = (
        settings.preview_subdivisions if mode == "preview" else settings.export_subdivisions
    )
    stride = max(1, 8 // subdivisions)
    terrain_mesh = terrain.build_terrain_mesh(
        dem=dem_array,
        transform=dem_transform,
        src_crs=dem_crs,
        target_crs=utm_crs,
        layout=layout,
        subdivisions=stride,
        base_thickness_mm=settings.min_base_thickness_mm,
    )
    logger.info(
        "terrain mesh: %d verts, %d faces, bounds=%s",
        len(terrain_mesh.vertices),
        len(terrain_mesh.faces),
        terrain_mesh.bounds.tolist(),
    )

    # 5. Clip the terrain to the shape polygon. Both the clip volume and the
    # visible frame extrude the SAME polygon, so their XY footprints are
    # bit-identical.
    clip_volume = frame.build_clip_volume(
        layout.shape_polygon_mm,
        z_min=float(terrain_mesh.bounds[0, 2]),
        z_max=float(terrain_mesh.bounds[1, 2]),
    )
    clipped_terrain = assembly.intersect(terrain_mesh, clip_volume)
    logger.info(
        "clipped terrain: %d verts, %d faces",
        len(clipped_terrain.vertices),
        len(clipped_terrain.faces),
    )

    # 6. Visible base frame, beneath z=0.
    frame_mesh = frame.build_frame(layout.shape_polygon_mm, settings.frame_thickness_mm)

    # 7. Track tube, cast onto the clipped terrain surface.
    track_mesh = track.build_track_tube(
        projected_track=projected,
        terrain_mesh=clipped_terrain,
        layout=layout,
        diameter_mm=settings.track_thickness_mm,
    )

    # 8. Final union.
    assembled = assembly.union([clipped_terrain, frame_mesh, track_mesh])
    logger.info(
        "assembled: %d verts, %d faces, watertight=%s",
        len(assembled.vertices),
        len(assembled.faces),
        assembled.is_watertight,
    )

    # 9. Export.
    export.export_mesh(assembled, output_path, export_format)

    return GenerateResult(
        output_filename=output_path.name,
        mode=mode,
        format=export_format,
        duration_seconds=round(time.perf_counter() - t0, 3),
        cache_hit=cache_hit,
        track_length_m=parsed.length_m,
        elevation_gain_m=parsed.elevation_gain_m,
        bbox=layout.dem_bbox_wgs84,
    )
