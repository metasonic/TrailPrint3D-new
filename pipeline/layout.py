"""Single source of truth for the model's spatial layout.

All builders (terrain, frame, clip volume, track tube) consume the same
`ModelLayout` so the geometry cannot drift between them. Two coordinate
frames are used:

  - UTM meters: the input track and the reprojected DEM.
  - Model mm: the final mesh space; (0, 0, 0) is the model centre on the
    base plane (terrain z>=0, frame z<=0).

The user-facing geometric rules implemented here:

  - Centring: the GPX track's 2D bbox centroid is mapped to the model origin.
  - Buffer: the terrain extends past the track's bbox by `buffer_mm` on every
    side. In `percent` mode, buffer_mm = max(model_size_mm * percent/100,
    buffer_min_mm). In `absolute` mode, buffer_mm = buffer_absolute_mm.
  - Shape sizing:
      - square: rectangle matching the buffered bbox (aspect ratio preserved).
      - circle: diameter equal to the diagonal of the buffered bbox.
      - hexagon: regular hexagon circumscribing the buffered bbox (flat-top
        or point-top selectable).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pyproj import CRS, Transformer
from shapely.geometry import Polygon

from backend.app.models import GenerateSettings

BBoxWGS84 = tuple[float, float, float, float]


@dataclass(frozen=True)
class ModelLayout:
    utm_centre: tuple[float, float]
    """Track bbox centroid in UTM meters. Everything is translated by -utm_centre."""

    utm_track_size: tuple[float, float]
    """Track bbox dimensions in UTM meters (width, height)."""

    scale: float
    """Millimetres per UTM metre. Same value used for X and Y."""

    z_scale: float
    """Vertical scale (scale * settings.terrain_scale). Applied to elevations."""

    buffer_mm: float
    """Effective buffer (in mm) added to the track bbox before shape sizing."""

    shape_polygon_mm: Polygon
    """The 2D footprint of the terrain and the frame, centred at origin (mm).
    Both `pipeline.frame.build_frame` and `pipeline.frame.build_clip_volume`
    extrude this *same* polygon — that's how they stay perfectly aligned."""

    dem_bbox_wgs84: BBoxWGS84
    """WGS84 bbox of the area to download for the DEM (shape bbox + safety margin)."""

    @property
    def shape_extent_mm(self) -> tuple[float, float]:
        minx, miny, maxx, maxy = self.shape_polygon_mm.bounds
        return (maxx - minx, maxy - miny)


def plan(
    projected_track: np.ndarray,
    utm_crs: CRS,
    settings: GenerateSettings,
) -> ModelLayout:
    """Compute the layout for one generate() invocation."""
    if projected_track.shape[0] < 2:
        raise ValueError("Track needs at least 2 points")

    min_xy = projected_track[:, :2].min(axis=0)
    max_xy = projected_track[:, :2].max(axis=0)
    track_w_m = float(max_xy[0] - min_xy[0])
    track_h_m = float(max_xy[1] - min_xy[1])
    track_longest_m = max(track_w_m, track_h_m)
    if track_longest_m <= 0:
        raise ValueError("Track has zero spatial extent")

    centre = (
        float((min_xy[0] + max_xy[0]) / 2.0),
        float((min_xy[1] + max_xy[1]) / 2.0),
    )

    # Scale: map the track's longest UTM dimension to model_size_mm.
    scale = settings.model_size_mm / track_longest_m

    # Buffer (in mm).
    if settings.buffer_mode == "percent":
        buffer_mm = max(
            settings.model_size_mm * settings.buffer_percent / 100.0,
            settings.buffer_min_mm,
        )
    else:
        buffer_mm = settings.buffer_absolute_mm

    # Buffered track bbox in mm.
    track_w_mm = track_w_m * scale
    track_h_mm = track_h_m * scale
    buffered_w_mm = track_w_mm + 2.0 * buffer_mm
    buffered_h_mm = track_h_mm + 2.0 * buffer_mm

    shape_polygon = _shape_polygon(
        settings.shape, settings.hexagon_orientation, buffered_w_mm, buffered_h_mm
    )

    dem_bbox_wgs84 = _dem_bbox(shape_polygon, scale, centre, utm_crs, settings.bbox_padding_percent)

    return ModelLayout(
        utm_centre=centre,
        utm_track_size=(track_w_m, track_h_m),
        scale=scale,
        z_scale=scale * settings.terrain_scale,
        buffer_mm=buffer_mm,
        shape_polygon_mm=shape_polygon,
        dem_bbox_wgs84=dem_bbox_wgs84,
    )


def _shape_polygon(
    shape: str, hexagon_orientation: str, width_mm: float, height_mm: float
) -> Polygon:
    """Centre-origin polygon for the requested shape, circumscribing a buffered
    bbox of (width_mm, height_mm)."""
    if shape == "square":
        hw = width_mm / 2.0
        hh = height_mm / 2.0
        return Polygon([(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)])

    if shape == "circle":
        radius = math.hypot(width_mm, height_mm) / 2.0
        segments = 96
        coords = [
            (
                radius * math.cos(2 * math.pi * i / segments),
                radius * math.sin(2 * math.pi * i / segments),
            )
            for i in range(segments)
        ]
        return Polygon(coords)

    if shape == "hexagon":
        if hexagon_orientation == "flat_top":
            # Flat-top: bbox is 2R wide, R*sqrt(3) tall. Vertices at 0°, 60°, ...
            radius = max(width_mm / 2.0, height_mm / math.sqrt(3))
            angle_offset = 0.0
        else:  # point_top
            # Point-top: bbox is R*sqrt(3) wide, 2R tall. Vertices at 30°, 90°, ...
            radius = max(width_mm / math.sqrt(3), height_mm / 2.0)
            angle_offset = math.pi / 6.0
        coords = [
            (
                radius * math.cos(angle_offset + 2 * math.pi * i / 6),
                radius * math.sin(angle_offset + 2 * math.pi * i / 6),
            )
            for i in range(6)
        ]
        return Polygon(coords)

    raise ValueError(f"unknown shape: {shape!r}")


def _dem_bbox(
    shape_polygon: Polygon,
    scale: float,
    centre_utm: tuple[float, float],
    utm_crs: CRS,
    safety: float,
) -> BBoxWGS84:
    """Project the shape polygon's UTM bbox back to WGS84 with a safety margin."""
    minx_mm, miny_mm, maxx_mm, maxy_mm = shape_polygon.bounds
    half_w_m = (maxx_mm - minx_mm) / 2.0 / scale * (1.0 + safety)
    half_h_m = (maxy_mm - miny_mm) / 2.0 / scale * (1.0 + safety)
    cx, cy = centre_utm
    corners = [
        (cx - half_w_m, cy - half_h_m),
        (cx + half_w_m, cy - half_h_m),
        (cx - half_w_m, cy + half_h_m),
        (cx + half_w_m, cy + half_h_m),
    ]
    transformer = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    lons, lats = transformer.transform(xs, ys)
    return (
        float(min(lons)),
        float(min(lats)),
        float(max(lons)),
        float(max(lats)),
    )
