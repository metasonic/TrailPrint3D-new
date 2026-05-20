"""Boundary polygon generation and extrusion.

Three shapes are supported: square, circle, hexagon. The polygon is sized to
inscribe the terrain's XY bounding box (so the union of the resulting frame
with the clipped terrain produces a clean "shaped map" base).
"""

from __future__ import annotations

import math

import numpy as np
import trimesh
from shapely.geometry import Polygon


def _shape_polygon(shape: str, half_size: float, segments: int = 64) -> Polygon:
    """Return a centred shapely polygon for the given shape, sized to `half_size`."""
    if shape == "square":
        s = half_size
        return Polygon([(-s, -s), (s, -s), (s, s), (-s, s)])
    if shape == "circle":
        circle_angles = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
        coords = [(half_size * math.cos(a), half_size * math.sin(a)) for a in circle_angles]
        return Polygon(coords)
    if shape == "hexagon":
        # Flat-top hexagon: vertices at 30°, 90°, 150°, ...
        hex_angles = [math.radians(30 + 60 * i) for i in range(6)]
        coords = [(half_size * math.cos(a), half_size * math.sin(a)) for a in hex_angles]
        return Polygon(coords)
    raise ValueError(f"unknown shape: {shape!r}")


def build_frame(
    shape: str,
    terrain_bounds: np.ndarray,
    thickness_mm: float,
) -> trimesh.Trimesh:
    """Build the visible base frame: 2D shape extruded by `thickness_mm` below z=0.

    Args:
        shape: "square" | "circle" | "hexagon"
        terrain_bounds: trimesh.Trimesh.bounds (2x3) of the centred terrain.
        thickness_mm: vertical extrusion height in mm.

    The returned mesh sits at z in [-thickness_mm, 0]. The terrain (whose base
    is at z=0) sits on top.
    """
    half_size = 0.5 * max(
        float(terrain_bounds[1, 0] - terrain_bounds[0, 0]),
        float(terrain_bounds[1, 1] - terrain_bounds[0, 1]),
    )
    poly = _shape_polygon(shape, half_size)
    mesh = trimesh.creation.extrude_polygon(poly, height=thickness_mm)
    # extrude_polygon goes from z=0 to z=thickness; translate so top sits at z=0
    mesh.apply_translation(np.array([0.0, 0.0, -thickness_mm]))
    return mesh


def build_clip_volume(
    shape: str,
    terrain_bounds: np.ndarray,
    margin_mm: float = 1.0,
) -> trimesh.Trimesh:
    """A vertical prism in the chosen shape, tall enough to fully contain the terrain.

    Used by assembly.union() to clip the rectangular terrain to the shape outline
    before unioning with the visible frame base. Sized identically to build_frame().
    """
    half_size = 0.5 * max(
        float(terrain_bounds[1, 0] - terrain_bounds[0, 0]),
        float(terrain_bounds[1, 1] - terrain_bounds[0, 1]),
    )
    poly = _shape_polygon(shape, half_size)
    z_min = float(terrain_bounds[0, 2]) - margin_mm
    z_max = float(terrain_bounds[1, 2]) + margin_mm
    mesh = trimesh.creation.extrude_polygon(poly, height=z_max - z_min)
    mesh.apply_translation(np.array([0.0, 0.0, z_min]))
    return mesh
