"""Frame and clip volume builders.

Both consume the *same* `shapely.Polygon` (computed once in
`pipeline.layout`), guaranteeing the terrain's clipped boundary, the visible
base frame, and the user-selected shape are pixel-identical.
"""

from __future__ import annotations

import numpy as np
import trimesh
from shapely.geometry import Polygon


def build_frame(polygon: Polygon, thickness_mm: float) -> trimesh.Trimesh:
    """Extrude `polygon` downwards from z=0 by `thickness_mm`.

    The returned mesh sits at z in [-thickness_mm, 0]. The clipped terrain
    sits on top with its base at z=0, so the two unions cleanly.
    """
    if thickness_mm <= 0:
        raise ValueError("frame thickness must be positive")
    mesh = trimesh.creation.extrude_polygon(polygon, height=thickness_mm)
    mesh.apply_translation(np.array([0.0, 0.0, -thickness_mm]))
    return mesh


def build_clip_volume(
    polygon: Polygon,
    z_min: float,
    z_max: float,
    margin_mm: float = 1.0,
) -> trimesh.Trimesh:
    """Extrude `polygon` vertically to fully contain [z_min, z_max].

    Used as the second operand of `pipeline.assembly.intersect` to crop the
    rectangular terrain mesh to the chosen shape's outline.
    """
    height = (z_max + margin_mm) - (z_min - margin_mm)
    if height <= 0:
        raise ValueError("clip volume needs z_max > z_min")
    mesh = trimesh.creation.extrude_polygon(polygon, height=height)
    mesh.apply_translation(np.array([0.0, 0.0, z_min - margin_mm]))
    return mesh
