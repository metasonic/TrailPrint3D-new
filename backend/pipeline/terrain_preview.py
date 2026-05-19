"""
Terrain mesh generator for quick preview — no Blender required.
Uses numpy for vertex/face generation and trimesh for mesh operations.

Coordinate system: Blender Z-up (X=east, Y=north, Z=elevation).
The preview_export module applies Y-up rotation for Three.js.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import trimesh

from .geo import mercator_x, mercator_y
from .elevation import ElevationConfig, get_elevations


@dataclass
class TerrainConfig:
    # Bounding box
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    # Mesh parameters
    num_subdivisions: int = 4       # 1-8; grid = (1 + 2^(n+1))^2 vertices
    elevation_scale: float = 1.0
    min_thickness: float = 2.0      # mm floor below lowest point
    # Scale
    obj_size_mm: float = 100.0
    # Shape
    shape: str = "HEXAGON"          # HEXAGON | SQUARE | CIRCLE | OCTAGON | ELLIPSE | HEART
    shape_rotation: float = 0.0     # degrees
    rectangle_height: float = 100.0
    ellipse_ratio: float = 0.75
    # When True, normalise elevation so the relief range spans 10 mm (matches addon autoScale)
    fixed_elevation_scale: bool = False


def _grid_size(num_subdivisions: int) -> int:
    return 1 + 2 ** (num_subdivisions + 1)


def build_terrain_mesh(
    config: TerrainConfig,
    elev_config: ElevationConfig,
    progress_cb=None,
) -> tuple[trimesh.Trimesh, float]:
    """
    Generate a terrain mesh for the given bounding box and settings.
    Returns (mesh, auto_scale) where auto_scale is the Z-scale factor (mm per
    elevation-km) used when building vertices; callers must pass it to
    build_trail_mesh so trail Z is consistent with terrain Z.
    """
    n = _grid_size(config.num_subdivisions)
    lats = np.linspace(config.min_lat, config.max_lat, n)
    lons = np.linspace(config.min_lon, config.max_lon, n)

    # Build a flat grid of (lat, lon) pairs for elevation lookup
    grid_lats, grid_lons = np.meshgrid(lats, lons, indexing="ij")
    coords = [(float(grid_lats[i, j]), float(grid_lons[i, j])) for i in range(n) for j in range(n)]

    # Fetch elevations
    elev_config.min_lat = config.min_lat
    elev_config.min_lon = config.min_lon
    elev_config.max_lat = config.max_lat
    elev_config.max_lon = config.max_lon
    elev_config.num_subdivisions = config.num_subdivisions

    elevations = get_elevations(coords, elev_config, progress_cb)
    elev_grid = np.array(elevations, dtype=np.float64).reshape(n, n)

    # Compute horizontal scale: map the widest extent to obj_size_mm
    xs = np.array([mercator_x(lon) for lon in lons])
    ys = np.array([mercator_y(lat) for lat in lats])
    width = xs[-1] - xs[0]
    height = ys[-1] - ys[0]
    span = max(abs(width), abs(height))
    if span == 0:
        span = 1.0
    scale_hor = config.obj_size_mm / span

    # Vertical scale: match addon's autoScale formula.
    # Normal mode: autoScale = scale_hor (elevation in same unit-space as x/y).
    # Fixed mode:  autoScale = 10 / (relief_km), so the elevation range is 10 mm.
    if config.fixed_elevation_scale:
        elev_diff = float(elev_grid.max() - elev_grid.min())
        auto_scale = (10.0 / (elev_diff / 1000.0)) if elev_diff > 0 else 10.0
    else:
        auto_scale = scale_hor

    # Build vertices — x,y,z all in mm-equivalent world units so min_thickness
    # (also in mm) can be subtracted directly in _add_floor.
    verts = np.zeros((n * n, 3), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            idx = i * n + j
            verts[idx, 0] = xs[j] * scale_hor
            verts[idx, 1] = ys[i] * scale_hor
            verts[idx, 2] = elev_grid[i, j] / 1000.0 * auto_scale * config.elevation_scale

    # Build faces (two triangles per quad)
    faces = []
    for i in range(n - 1):
        for j in range(n - 1):
            tl = i * n + j
            tr = i * n + j + 1
            bl = (i + 1) * n + j
            br = (i + 1) * n + j + 1
            faces.append([tl, tr, br])
            faces.append([tl, br, bl])

    terrain = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)

    # Clip to shape
    terrain = _clip_to_shape(terrain, config)

    if len(terrain.faces) == 0:
        raise ValueError(
            "Shape clip produced an empty mesh — try a different shape, rotation, or size"
        )

    # Add floor (min_thickness below lowest point)
    terrain = _add_floor(terrain, config.min_thickness)

    return terrain, auto_scale


def _clip_to_shape(mesh: trimesh.Trimesh, config: TerrainConfig) -> trimesh.Trimesh:
    """Remove vertices outside the chosen shape boundary."""
    cx = (mercator_x(config.min_lon) + mercator_x(config.max_lon)) / 2
    cy = (mercator_y(config.min_lat) + mercator_y(config.max_lat)) / 2

    # Compute scale_hor
    xs_span = abs(mercator_x(config.max_lon) - mercator_x(config.min_lon))
    ys_span = abs(mercator_y(config.max_lat) - mercator_y(config.min_lat))
    span = max(xs_span, ys_span)
    if span == 0:
        span = 1.0
    scale_hor = config.obj_size_mm / span
    cx_w = cx * scale_hor
    cy_w = cy * scale_hor

    half = config.obj_size_mm / 2.0
    rot_rad = math.radians(config.shape_rotation)

    verts = mesh.vertices.copy()
    vx = verts[:, 0] - cx_w
    vy = verts[:, 1] - cy_w

    # Rotate
    if config.shape_rotation != 0:
        c, s = math.cos(-rot_rad), math.sin(-rot_rad)
        vx_r = vx * c - vy * s
        vy_r = vx * s + vy * c
    else:
        vx_r, vy_r = vx, vy

    shape = config.shape.upper()

    if shape == "SQUARE":
        h_half = (config.rectangle_height / config.obj_size_mm) * half
        inside = (np.abs(vx_r) <= half) & (np.abs(vy_r) <= h_half)
    elif shape == "CIRCLE":
        inside = (vx_r ** 2 + vy_r ** 2) <= half ** 2
    elif shape == "HEXAGON":
        inside = _hex_inside(vx_r, vy_r, half)
    elif shape == "OCTAGON":
        inside = _octagon_inside(vx_r, vy_r, half)
    elif shape == "ELLIPSE":
        a, b = half, half * config.ellipse_ratio
        inside = (vx_r / a) ** 2 + (vy_r / b) ** 2 <= 1.0
    elif shape == "HEART":
        # Simple heart approximation
        inside = _heart_inside(vx_r, vy_r, half)
    else:
        inside = np.ones(len(verts), dtype=bool)

    # Keep faces where all three vertices are inside
    faces = mesh.faces
    v_inside = inside
    face_mask = v_inside[faces[:, 0]] & v_inside[faces[:, 1]] & v_inside[faces[:, 2]]
    clipped = trimesh.Trimesh(vertices=mesh.vertices, faces=faces[face_mask], process=False)
    clipped.remove_unreferenced_vertices()
    return clipped


def points_inside_shape(world_pts_xy: np.ndarray, config: TerrainConfig) -> np.ndarray:
    """Return boolean mask for arbitrary (N,2) world-space XY points.

    Shares the same boundary logic as _clip_to_shape so trail-point filtering
    and mesh clipping are always consistent.
    """
    cx = (mercator_x(config.min_lon) + mercator_x(config.max_lon)) / 2
    cy = (mercator_y(config.min_lat) + mercator_y(config.max_lat)) / 2
    xs_span = abs(mercator_x(config.max_lon) - mercator_x(config.min_lon))
    ys_span = abs(mercator_y(config.max_lat) - mercator_y(config.min_lat))
    span = max(xs_span, ys_span) or 1.0
    scale_hor = config.obj_size_mm / span
    cx_w, cy_w = cx * scale_hor, cy * scale_hor
    half = config.obj_size_mm / 2.0
    rot_rad = math.radians(config.shape_rotation)

    vx = world_pts_xy[:, 0] - cx_w
    vy = world_pts_xy[:, 1] - cy_w
    if config.shape_rotation != 0:
        c, s = math.cos(-rot_rad), math.sin(-rot_rad)
        vx, vy = vx * c - vy * s, vx * s + vy * c

    shape = config.shape.upper()
    if shape == "SQUARE":
        h_half = (config.rectangle_height / config.obj_size_mm) * half
        return (np.abs(vx) <= half) & (np.abs(vy) <= h_half)
    elif shape == "CIRCLE":
        return vx ** 2 + vy ** 2 <= half ** 2
    elif shape == "HEXAGON":
        return _hex_inside(vx, vy, half)
    elif shape == "OCTAGON":
        return _octagon_inside(vx, vy, half)
    elif shape == "ELLIPSE":
        a, b = half, half * config.ellipse_ratio
        return (vx / a) ** 2 + (vy / b) ** 2 <= 1.0
    elif shape == "HEART":
        return _heart_inside(vx, vy, half)
    return np.ones(len(world_pts_xy), dtype=bool)


def _hex_inside(vx: np.ndarray, vy: np.ndarray, r: float) -> np.ndarray:
    """Flat-top hexagon test."""
    q2x = np.abs(vx)
    q2y = np.abs(vy)
    return (q2x <= r) & (q2y <= r * math.sqrt(3) / 2) & (
        q2x * math.sqrt(3) / 2 + q2y / 2 <= r * math.sqrt(3) / 2
    )


def _octagon_inside(vx: np.ndarray, vy: np.ndarray, r: float) -> np.ndarray:
    ax, ay = np.abs(vx), np.abs(vy)
    k = math.sqrt(2) - 1
    return (ax <= r) & (ay <= r) & (ax + ay <= r * (1 + k))


def _heart_inside(vx: np.ndarray, vy: np.ndarray, r: float) -> np.ndarray:
    # Unit heart (x²+y²-1)³−x²y³≤0 has max radial extent ≈1.4245 at θ≈±60°.
    # Scale so the heart fits within radius r.
    _HEART_MAX_R = 1.42455  # true max radial extent at θ ≈ 50.77°
    x = vx * (_HEART_MAX_R / r)
    y = vy * (_HEART_MAX_R / r)
    val = (x ** 2 + y ** 2 - 1) ** 3 - x ** 2 * y ** 3
    return val <= 0


def _add_floor(mesh: trimesh.Trimesh, min_thickness: float) -> trimesh.Trimesh:
    """Extrude the mesh downward by min_thickness (mm, same units as x/y/z) to create a solid base."""
    if len(mesh.vertices) == 0:
        return mesh

    z_min = mesh.vertices[:, 2].min()
    floor_z = z_min - min_thickness  # both already in mm-equivalent world units

    # Create floor vertices (same XY, fixed Z)
    top_verts = mesh.vertices.copy()
    bot_verts = top_verts.copy()
    bot_verts[:, 2] = floor_z

    n_top = len(top_verts)
    all_verts = np.vstack([top_verts, bot_verts])

    # Top faces (original)
    top_faces = mesh.faces.copy()
    # Bottom faces (flipped normals)
    bot_faces = mesh.faces.copy() + n_top
    bot_faces = bot_faces[:, ::-1]

    # Side faces along boundary edges.
    # mesh.edges (not mesh.edges_unique) must be used here:
    # interior edges appear twice in mesh.edges, boundary edges appear once.
    # group_rows with require_count=1 finds the boundary-only edges.
    all_edges = mesh.edges
    all_edges_sorted = np.sort(all_edges, axis=1)
    boundary_indices = trimesh.grouping.group_rows(all_edges_sorted, require_count=1)
    side_faces = []
    for edge_idx in boundary_indices:
        v0, v1 = all_edges[edge_idx]
        b0, b1 = v0 + n_top, v1 + n_top
        # Winding order: outward-facing normals require v1→v0 on side quads.
        # Top surface uses CCW convention viewed from above; boundary edges are
        # directed CCW, so reversing to v1,v0 on the side makes normals point out.
        side_faces.append([v1, v0, b0])
        side_faces.append([v1, b0, b1])

    all_faces = np.vstack([top_faces, bot_faces] + ([np.array(side_faces)] if side_faces else []))
    solid = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=False)
    return solid
