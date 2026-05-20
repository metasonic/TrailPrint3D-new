"""GPX parsing, UTM projection, and Frenet-frame tube extrusion.

Public surface locked in docs/phase2_pipeline_design.md. The brief specifies a
Frenet-frame algorithm; we use the rotation-minimizing variant (parallel
transport) because the pure Frenet frame is undefined where curvature is zero
(straight segments) and flips at sharp turns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gpxpy
import numpy as np
import trimesh
from pyproj import CRS, Transformer
from shapely.geometry import Point

BBoxWGS84 = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


@dataclass(frozen=True)
class Track:
    """Parsed GPX track. Points are (lon, lat, elevation_m); elevation may be 0 if absent."""

    points: np.ndarray  # Nx3 float64
    name: str | None
    length_m: float
    elevation_gain_m: float


def load_track(gpx_path: Path) -> Track:
    """Parse a GPX file. Concatenates all tracks and segments in source order."""
    with gpx_path.open("r", encoding="utf-8") as fh:
        gpx = gpxpy.parse(fh)
    rows: list[tuple[float, float, float]] = []
    name: str | None = None
    for trk in gpx.tracks:
        if name is None and trk.name:
            name = trk.name
        for seg in trk.segments:
            for pt in seg.points:
                rows.append((pt.longitude, pt.latitude, pt.elevation or 0.0))
    if not rows:
        raise ValueError(f"GPX contains no track points: {gpx_path}")
    points = np.asarray(rows, dtype=np.float64)
    length_m = float(gpx.length_3d() or gpx.length_2d() or 0.0)
    uphill, _ = gpx.get_uphill_downhill()
    return Track(points=points, name=name, length_m=length_m, elevation_gain_m=float(uphill))


def pick_utm_crs(track: Track) -> CRS:
    """Pick the UTM zone for the track centroid. Latitude-aware (N vs S)."""
    centroid_lon = float(track.points[:, 0].mean())
    centroid_lat = float(track.points[:, 1].mean())
    zone = int((centroid_lon + 180.0) / 6.0) + 1
    epsg = 32600 + zone if centroid_lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def project_to_utm(track: Track, target_crs: CRS) -> np.ndarray:
    """Return an Nx3 array of (easting_m, northing_m, elevation_m)."""
    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    east, north = transformer.transform(track.points[:, 0], track.points[:, 1])
    return np.column_stack([east, north, track.points[:, 2]])


def compute_bbox(track: Track, padding: float) -> BBoxWGS84:
    """Track WGS84 bbox grown by `padding` fraction (0..1) in each direction."""
    lon_min = float(track.points[:, 0].min())
    lon_max = float(track.points[:, 0].max())
    lat_min = float(track.points[:, 1].min())
    lat_max = float(track.points[:, 1].max())
    dlon = (lon_max - lon_min) * padding
    dlat = (lat_max - lat_min) * padding
    return (lon_min - dlon, lat_min - dlat, lon_max + dlon, lat_max + dlat)


def _cast_track_onto_mesh(projected_track: np.ndarray, terrain: trimesh.Trimesh) -> np.ndarray:
    """Replace each track point's Z with the Z of the terrain directly below it.

    Uses trimesh.ray (which uses the embree backend when available, falling back
    to a pure-Python ray-triangle test). Track points that miss the terrain
    keep their original Z.
    """
    origins = projected_track.copy()
    z_max = float(terrain.bounds[1, 2]) + 1.0
    origins[:, 2] = z_max
    directions = np.tile(np.array([0.0, 0.0, -1.0]), (len(origins), 1))
    locations, index_ray, _ = terrain.ray.intersects_location(
        ray_origins=origins, ray_directions=directions, multiple_hits=False
    )
    cast = projected_track.copy()
    if len(index_ray):
        cast[index_ray, 2] = locations[:, 2]
    return cast


def build_track_tube(
    projected_track: np.ndarray,
    terrain_mesh: trimesh.Trimesh,
    diameter_mm: float,
    xy_scale: float,
    z_scale: float,
    segments: int = 12,
) -> trimesh.Trimesh:
    """Sweep a circular cross-section along the path. Watertight by construction.

    Uses trimesh.creation.sweep_polygon, which builds parallel-transport frames
    internally and caps both ends. We hand it the GPX path snapped onto the
    already-scaled terrain.

    Args:
        projected_track: Nx3 UTM coordinates in meters (pre-scale).
        terrain_mesh: the already-scaled terrain, used to cast Z onto.
        diameter_mm: tube outer diameter in the final model's mm.
        xy_scale: factor that maps UTM meters to model mm in XY.
        z_scale: factor applied to elevation (matches terrain's vertical scale).
        segments: cross-section segment count (default 12 = clean circle, low poly).
    """
    if len(projected_track) < 2:
        raise ValueError("Track needs at least 2 points to extrude a tube")

    # Terrain was first translated by -utm_centre (in UTM meters), then scaled
    # by xy_scale. The track must follow the same order: shift in UTM meters,
    # then scale — otherwise the track lands tens of km off origin while the
    # terrain sits at the origin in mm space.
    utm_centre_x, utm_centre_y = terrain_mesh.metadata.get("utm_centre", (0.0, 0.0))
    scaled = projected_track.copy()
    scaled[:, 0] = (scaled[:, 0] - utm_centre_x) * xy_scale
    scaled[:, 1] = (scaled[:, 1] - utm_centre_y) * xy_scale
    scaled[:, 2] *= z_scale
    snapped = _cast_track_onto_mesh(scaled, terrain_mesh)
    snapped[:, 2] += diameter_mm * 0.5  # lift slightly so the union doesn't z-fight

    # Drop consecutive duplicates (gpxpy occasionally emits them at segment joins).
    keep = np.concatenate([[True], np.any(np.diff(snapped, axis=0) != 0, axis=1)])
    snapped = snapped[keep]
    if len(snapped) < 2:
        raise ValueError("Track collapsed to a single point after de-duplication")

    cross_section = Point(0.0, 0.0).buffer(diameter_mm * 0.5, quad_segs=max(3, segments // 4))
    tube = trimesh.creation.sweep_polygon(cross_section, snapped)
    if not tube.is_volume:
        tube.fix_normals()
    if not tube.is_volume:
        raise RuntimeError("track tube is not a valid volume after sweep_polygon")
    return tube
