"""Orchestrator: GPX in, 3D printable mesh out. Pure Python, no Blender."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.app.models import ExportFormat, GenerateMode, GenerateResult, GenerateSettings
from pipeline import assembly, export, frame, terrain, track

logger = logging.getLogger(__name__)


def generate(
    gpx_path: Path,
    settings: GenerateSettings,
    output_path: Path,
    mode: GenerateMode,
    export_format: ExportFormat,
) -> GenerateResult:
    """Run the full pipeline. See docs/phase2_pipeline_design.md for the contract.

    Geometry decisions (logged in MEMORY.md, Phase 4 entry):
      1. Terrain is built oversized over the DEM bbox, then INTERSECTED with a
         vertical prism in the chosen frame shape. This makes the `shape`
         parameter visually meaningful instead of letting the terrain corners
         poke past the frame outline.
      2. Track points are cast onto the DEM surface (matches the original
         addon's `overwrite_path_elevation=True` default).
    """
    t0 = time.perf_counter()

    # 1. Track
    parsed = track.load_track(gpx_path)
    utm_crs = track.pick_utm_crs(parsed)
    projected = track.project_to_utm(parsed, utm_crs)
    bbox = track.compute_bbox(parsed, padding=settings.bbox_padding_percent)

    # 2. DEM
    dem_array, dem_transform, dem_crs, cache_hit = terrain.fetch_dem(bbox)

    # 3. Terrain mesh (subdivisions vary by mode)
    subdivisions = (
        settings.preview_subdivisions if mode == "preview" else settings.export_subdivisions
    )
    # subdivisions is a "downsampling stride": preview uses a larger stride.
    # The schema's "preview=2 / export=4" maps inversely (preview coarser, export finer):
    # invert it here so a higher field value → finer detail.
    stride = max(1, 8 // subdivisions)
    terrain_mesh = terrain.build_terrain_mesh(
        dem=dem_array,
        transform=dem_transform,
        src_crs=dem_crs,
        target_crs=utm_crs,
        subdivisions=stride,
        scale=settings.terrain_scale,
        base_thickness=settings.min_base_thickness_mm,
        model_size_mm=settings.model_size_mm,
    )
    logger.info(
        "terrain mesh: %d verts, %d faces, bounds=%s",
        len(terrain_mesh.vertices),
        len(terrain_mesh.faces),
        terrain_mesh.bounds.tolist(),
    )

    # 4. Clip terrain to the chosen frame outline
    clip_volume = frame.build_clip_volume(settings.shape, terrain_mesh.bounds)
    clipped_terrain = assembly.intersect(terrain_mesh, clip_volume)
    # Preserve metadata the track tube needs (xy_scale, centre)
    clipped_terrain.metadata.update(terrain_mesh.metadata)
    logger.info(
        "clipped terrain: %d verts, %d faces",
        len(clipped_terrain.vertices),
        len(clipped_terrain.faces),
    )

    # 5. Visible base frame, sized to match the clipped terrain
    frame_mesh = frame.build_frame(
        shape=settings.shape,
        terrain_bounds=clipped_terrain.bounds,
        thickness_mm=settings.frame_thickness_mm,
    )

    # 6. Track tube (cast onto the clipped terrain)
    xy_scale = float(clipped_terrain.metadata["xy_scale"])
    z_scale = float(clipped_terrain.metadata["z_scale"])
    track_mesh = track.build_track_tube(
        projected_track=projected,
        terrain_mesh=clipped_terrain,
        diameter_mm=settings.track_thickness_mm,
        xy_scale=xy_scale,
        z_scale=z_scale,
    )

    # 7. Final union
    assembled = assembly.union([clipped_terrain, frame_mesh, track_mesh])
    logger.info(
        "assembled: %d verts, %d faces, watertight=%s",
        len(assembled.vertices),
        len(assembled.faces),
        assembled.is_watertight,
    )

    # 8. Export
    export.export_mesh(assembled, output_path, export_format)

    return GenerateResult(
        output_filename=output_path.name,
        mode=mode,
        format=export_format,
        duration_seconds=round(time.perf_counter() - t0, 3),
        cache_hit=cache_hit,
        track_length_m=parsed.length_m,
        elevation_gain_m=parsed.elevation_gain_m,
        bbox=bbox,
    )
