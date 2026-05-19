"""
Trail path extrusion for the quick-preview pipeline.
Generates a tube mesh along the GPX track, cast onto the terrain surface.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

import numpy as np
import trimesh

from .geo import mercator_x, mercator_y


def build_trail_mesh(
    track_points: list[tuple[float, float, float]],   # (lat, lon, elev_m)
    terrain: trimesh.Trimesh,
    obj_size_mm: float,
    path_thickness: float,
    scale_hor: float,
    scale_z: Optional[float] = None,
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
    scale_z        : vertical scale factor; defaults to scale_hor.
                     Must be set to terrain's auto_scale when fixed_elevation_scale
                     is True so trail Z is consistent with terrain Z.
    scale_elevation: elevation multiplier
    overwrite_elevation: cast path Z onto terrain surface
    """
    if len(track_points) < 2:
        return None

    _scale_z = scale_z if scale_z is not None else scale_hor

    # Convert track points to world space.
    # When overwrite_elevation=True the Z is replaced by ray casting anyway;
    # when False, use the same auto_scale as terrain so units are consistent.
    world_pts = np.array([
        [
            mercator_x(lon) * scale_hor,
            mercator_y(lat) * scale_hor,
            elev / 1000.0 * _scale_z * scale_elevation,
        ]
        for lat, lon, elev in track_points
    ], dtype=np.float64)

    # Cast points onto terrain surface via ray casting downward
    if overwrite_elevation and len(terrain.vertices) > 0:
        world_pts = _cast_on_terrain(world_pts, terrain)

    # Raise path by one full radius so the tube sits on the terrain surface
    # rather than half-embedded in it.
    world_pts[:, 2] += path_thickness / 2

    tube = _build_tube(world_pts, radius=path_thickness / 2, sections=6)
    return tube


def _cast_on_terrain(pts: np.ndarray, terrain: trimesh.Trimesh) -> np.ndarray:
    """Raycast each point downward onto the terrain, replace Z with hit Z.

    Requests all hits per ray and keeps the highest-Z intersection so that
    side-wall and floor faces added by _add_floor are ignored — the top
    terrain surface always produces the highest Z value.
    """
    result = pts.copy()
    ray_origins = pts.copy()
    z_min = terrain.vertices[:, 2].min()
    z_max = terrain.vertices[:, 2].max()
    ray_origins[:, 2] = z_max + max(10.0, (z_max - z_min) * 0.05)
    ray_dirs = np.tile([0, 0, -1], (len(pts), 1)).astype(np.float64)

    try:
        locations, index_ray, _ = terrain.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_dirs,
            multiple_hits=True,
        )
        # For each ray pick the highest-Z hit (= top terrain surface).
        best: dict[int, float] = {}
        for ray_idx, loc in zip(index_ray, locations):
            if ray_idx not in best or loc[2] > best[ray_idx]:
                best[ray_idx] = float(loc[2])
        for ray_idx, z in best.items():
            result[ray_idx, 2] = z
    except Exception:
        logger.debug("Ray cast onto terrain failed; using original GPX elevation", exc_info=True)

    return result


def _build_tube(
    path: np.ndarray,
    radius: float,
    sections: int = 6,
) -> trimesh.Trimesh:
    """Create a tube mesh along a polyline path.

    One ring is generated per path point and shared between adjacent segments,
    producing a fully connected (manifold) tube with no open seams at waypoints.
    """
    n = len(path)
    verts: list = []
    faces: list = []

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
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tang, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0])
        right = np.cross(tang, up)
        right /= np.linalg.norm(right)
        up = np.cross(right, tang)
        return right, up

    # One ring per path point — shared between adjacent segments.
    # Interior points use the forward segment direction; the last point uses the
    # previous-segment direction so the frame is continuous at the tip.
    for i in range(n):
        if i < n - 1:
            right, up = _frame(path[i], path[i + 1])
        else:
            right, up = _frame(path[i - 1], path[i])
        ring = path[i] + radius * (circle[:, 0:1] * right + circle[:, 1:2] * up)
        verts.extend(ring.tolist())

    # Connect adjacent rings with quads (two triangles each)
    for i in range(n - 1):
        base = i * sections
        next_base = (i + 1) * sections
        for j in range(sections):
            j2 = (j + 1) % sections
            faces.append([base + j, base + j2, next_base + j2])
            faces.append([base + j, next_base + j2, next_base + j])

    # Start cap (inward-facing — CW when viewed from outside)
    center_s = len(verts)
    verts.append(path[0].tolist())
    for j in range(sections):
        j2 = (j + 1) % sections
        faces.append([center_s, j2, j])

    # End cap
    center_e = len(verts)
    last_ring_base = (n - 1) * sections
    verts.append(path[-1].tolist())
    for j in range(sections):
        j2 = (j + 1) % sections
        faces.append([center_e, last_ring_base + j, last_ring_base + j2])

    mesh = trimesh.Trimesh(
        vertices=np.array(verts, dtype=np.float64),
        faces=np.array(faces),
        process=False,
    )
    # Body-face winding is inward by construction; reverse all face indices so
    # normals point outward (positive volume = correct for 3D printing / Three.js).
    mesh.faces = mesh.faces[:, ::-1]
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
