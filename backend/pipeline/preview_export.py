"""
Assemble terrain + trail meshes into a glTF/GLB file for Three.js.

Coordinate transform: Blender Z-up → Three.js Y-up
  (rotate -90° around X axis: Y→Z, Z→-Y)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import trimesh
import trimesh.transformations as tf


# Rotation matrix: Blender Z-up → Three.js Y-up (-90° around X)
_R_YUP = tf.rotation_matrix(-np.pi / 2, [1, 0, 0])


def _apply_yup(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return a new mesh with vertices rotated to Y-up coordinates."""
    verts = trimesh.transform_points(mesh.vertices, _R_YUP)
    return trimesh.Trimesh(vertices=verts, faces=mesh.faces, process=False)


def export_preview_glb(
    terrain: trimesh.Trimesh,
    trail: Optional[trimesh.Trimesh],
    out_path: Path,
) -> None:
    """
    Export terrain and optional trail to a single GLB file.
    Applies XY centering (so the terrain is centred at the world origin),
    Y-up rotation, and PBR materials.

    Centering is applied to both terrain and trail using the terrain's XY
    bounding-box centre so that Three.js OrbitControls and camera setup can
    assume the model is at the origin without further adjustment.
    """
    scene = trimesh.Scene()

    # Compute the XY centre of the terrain bounding box.
    # Both terrain and trail share the same absolute Mercator coordinate space,
    # so subtracting this single offset centres the entire scene.
    t_min = terrain.vertices[:, :2].min(axis=0)
    t_max = terrain.vertices[:, :2].max(axis=0)
    xy_centre = (t_min + t_max) / 2.0

    def _centre_and_yup(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        verts = mesh.vertices.copy()
        verts[:, :2] -= xy_centre
        rotated = trimesh.transform_points(verts, _R_YUP)
        return trimesh.Trimesh(vertices=rotated, faces=mesh.faces, process=False)

    terrain_yup = _centre_and_yup(terrain)
    terrain_yup.visual = trimesh.visual.ColorVisuals(
        mesh=terrain_yup,
        vertex_colors=np.tile([180, 180, 180, 255], (len(terrain_yup.vertices), 1)),
    )
    scene.add_geometry(terrain_yup, geom_name="terrain", node_name="terrain")

    if trail is not None and len(trail.vertices) > 0:
        trail_yup = _centre_and_yup(trail)
        trail_yup.visual = trimesh.visual.ColorVisuals(
            mesh=trail_yup,
            vertex_colors=np.tile([220, 50, 50, 255], (len(trail_yup.vertices), 1)),
        )
        scene.add_geometry(trail_yup, geom_name="trail", node_name="trail")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(str(out_path), file_type="glb")


def generate_preview(
    gpx_path: Path,
    settings,  # GenerationSettings
    out_path: Path,
    elev_config,  # ElevationConfig
    progress_cb=None,
) -> dict:
    """
    Full preview generation pipeline:
      1. Parse GPX
      2. Fetch elevation grid
      3. Build terrain mesh
      4. Build trail tube
      5. Export GLB
    Returns terrain stats dict.
    """
    from .gpx_parser import read_track_file, compute_track_stats, flatten_segments
    from .terrain_preview import TerrainConfig, build_terrain_mesh
    from .trail_preview import build_trail_mesh, compute_scale_hor
    from .geo import bbox_for_track

    # 1. Parse GPX
    segments = read_track_file(gpx_path)
    stats = compute_track_stats(segments)
    track_points = flatten_segments(segments)

    # 2. Determine bbox with padding
    bbox = bbox_for_track(
        stats.min_lat, stats.min_lon,
        stats.max_lat, stats.max_lon,
        padding_km=2.0,
    )

    # 3. Build terrain
    tconf = TerrainConfig(
        min_lat=bbox[0],
        min_lon=bbox[1],
        max_lat=bbox[2],
        max_lon=bbox[3],
        num_subdivisions=min(settings.num_subdivisions, 4),  # cap preview at 4
        elevation_scale=settings.elevation_scale,
        min_thickness=settings.min_thickness,
        obj_size_mm=settings.obj_size_mm,
        shape=settings.shape,
        shape_rotation=float(settings.shape_rotation),
        rectangle_height=float(settings.rectangle_height),
        ellipse_ratio=settings.ellipse_ratio,
        fixed_elevation_scale=getattr(settings, "fixed_elevation_scale", False),
    )
    elev_config.min_lat = bbox[0]
    elev_config.min_lon = bbox[1]
    elev_config.max_lat = bbox[2]
    elev_config.max_lon = bbox[3]

    terrain = build_terrain_mesh(tconf, elev_config, progress_cb)

    # 4. Build trail tube
    scale_hor = compute_scale_hor(
        bbox[0], bbox[1], bbox[2], bbox[3], settings.obj_size_mm
    )
    trail_pts = [(p[0], p[1], p[2]) for p in track_points]
    trail = build_trail_mesh(
        trail_pts,
        terrain,
        obj_size_mm=settings.obj_size_mm,
        path_thickness=settings.path_thickness,
        scale_hor=scale_hor,
        scale_elevation=settings.elevation_scale,
        overwrite_elevation=settings.overwrite_path_elevation,
    )

    # 5. Export GLB
    export_preview_glb(terrain, trail, out_path)

    return {
        "vertex_count": len(terrain.vertices) + (len(trail.vertices) if trail else 0),
        "face_count": len(terrain.faces) + (len(trail.faces) if trail else 0),
        "bbox": bbox,
        "track_length_km": stats.length_km,
    }
