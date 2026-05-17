"""
Trail path extrusion for the quick-preview pipeline.
Generates a tube mesh along the GPX track, cast onto the terrain surface.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import trimesh

from .geo import mercator_x, mercator_y


def build_trail_mesh(
    track_points: list[tuple[float, float, float]],   # (lat, lon, elev_m)
    terrain: trimesh.Trimesh,
    obj_size_mm: float,
    path_thickness: float,
    scale_hor: float,
    scale_elevation: float = 1.0,
    overwrite_elevation: bool = True,
    progress_cb=None,
) -> Optional[trimesh.Trimesh]:
    """
    Extrude the GPX track as a round tube on the terrain surface.

    Parameters
    ----------
    track_points   : (lat, lon, elev_m) tuples from the GPX parser
    terrain        : terrain mesh (Z-up, world space)
    obj_size_mm    : used to recover scale_hor
    path_thickness : tube diameter in mm
    scale_hor      : horizontal scale factor (mm/mercator-unit)
    scale_elevation: elevation multiplier
    overwrite_elevation: cast path Z onto terrain surface
    """
    if len(track_points) < 2:
        return None

    # Convert track points to world space
    world_pts = np.array([
        [
            mercator_x(lon) * scale_hor,
            mercator_y(lat) * scale_hor,
            elev / 1000.0 * scale_elevation,
        ]
        for lat, lon, elev in track_points
    ], dtype=np.float64)

    # Cast points onto terrain surface via ray casting downward
    if overwrite_elevation and len(terrain.vertices) > 0:
        world_pts = _cast_on_terrain(world_pts, terrain)

    # Raise path slightly above surface to avoid z-fighting
    world_pts[:, 2] += path_thickness * 0.001

    tube = _build_tube(world_pts, radius=path_thickness / 2, sections=6)
    return tube


def _cast_on_terrain(pts: np.ndarray, terrain: trimesh.Trimesh) -> np.ndarray:
    """Raycast each point downward onto the terrain, replace Z with hit Z."""
    result = pts.copy()
    ray_origins = pts.copy()
    ray_origins[:, 2] = terrain.vertices[:, 2].max() + 10
    ray_dirs = np.tile([0, 0, -1], (len(pts), 1)).astype(np.float64)

    try:
        locations, index_ray, _ = terrain.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_dirs,
            multiple_hits=False,
        )
        for i, loc in zip(index_ray, locations):
            result[i, 2] = loc[2]
    except Exception:
        pass  # fall back to original Z

    return result


def _build_tube(
    path: np.ndarray,
    radius: float,
    sections: int = 6,
) -> trimesh.Trimesh:
    """Create a tube mesh along a polyline path."""
    n = len(path)
    verts = []
    faces = []

    angles = np.linspace(0, 2 * math.pi, sections, endpoint=False)
    circle = np.column_stack([np.cos(angles), np.sin(angles)])

    def _frame(p0, p1):
        """Compute a right-hand frame for segment p0→p1."""
        tang = p1 - p0
        tang_norm = np.linalg.norm(tang)
        if tang_norm < 1e-12:
            tang = np.array([0.0, 0.0, 1.0])
        else:
            tang = tang / tang_norm
        # Choose an up vector not parallel to tang
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tang, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0])
        right = np.cross(tang, up)
        right /= np.linalg.norm(right)
        up = np.cross(right, tang)
        return right, up

    ring_start = 0
    for i in range(n - 1):
        p0, p1 = path[i], path[i + 1]
        right, up = _frame(p0, p1)

        ring = p0 + radius * (circle[:, 0:1] * right + circle[:, 1:2] * up)
        ring_next = p1 + radius * (circle[:, 0:1] * right + circle[:, 1:2] * up)

        base = ring_start
        verts.extend(ring.tolist())
        verts.extend(ring_next.tolist())

        for j in range(sections):
            j2 = (j + 1) % sections
            a, b = base + j, base + j2
            c, d = base + sections + j, base + sections + j2
            faces.append([a, b, d])
            faces.append([a, d, c])

        ring_start += sections * 2

    # Caps
    # Start cap
    center_s = len(verts)
    verts.append(path[0].tolist())
    for j in range(sections):
        j2 = (j + 1) % sections
        faces.append([center_s, j2, j])

    # End cap
    center_e = len(verts)
    last_ring_base = ring_start - sections
    verts.append(path[-1].tolist())
    for j in range(sections):
        j2 = (j + 1) % sections
        faces.append([center_e, last_ring_base + j, last_ring_base + j2])

    mesh = trimesh.Trimesh(
        vertices=np.array(verts, dtype=np.float64),
        faces=np.array(faces),
        process=False,
    )
    return mesh


def compute_scale_hor(
    min_lat: float, min_lon: float,
    max_lat: float, max_lon: float,
    obj_size_mm: float,
) -> float:
    """Replicate geo.py's calculate_scale for the FACTOR/COORDINATES mode."""
    x1, x2 = mercator_x(min_lon), mercator_x(max_lon)
    y1, y2 = mercator_y(min_lat), mercator_y(max_lat)
    span = max(abs(x2 - x1), abs(y2 - y1))
    if span == 0:
        return 1.0
    return obj_size_mm / span
