"""
Geospatial coordinate utilities — extracted from TrailPrint3D/utils/geo.py.
All bpy dependencies removed; parameters are passed explicitly.
"""
from __future__ import annotations

import math

R = 6371.0  # Earth radius in km


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def mercator_x(lon: float) -> float:
    return R * math.radians(lon)


def mercator_y(lat: float) -> float:
    # Clamp to Web Mercator valid range to avoid log(tan(pi/2)) = inf at lat=±90
    lat = max(-85.051129, min(85.051129, lat))
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def convert_to_world(
    lat: float,
    lon: float,
    elevation: float,
    scale_elevation: float = 1.0,
    auto_scale: float = 1.0,
    scale_hor: float = 1.0,
) -> tuple[float, float, float]:
    """Convert geographic coordinates to Blender/world-space (Z-up)."""
    x = R * math.radians(lon) * scale_hor
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * scale_hor
    z = elevation / 1000.0 * scale_elevation * auto_scale
    return (x, y, z)


def convert_to_neutral(
    lat: float,
    lon: float,
    elevation: float,
    scale_elevation: float = 1.0,
    auto_scale: float = 1.0,
) -> tuple[float, float, float]:
    """Mercator projection without horizontal scale factor."""
    x = R * math.radians(lon)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    z = elevation / 1000.0 * scale_elevation * auto_scale
    return (x, y, z)


def calculate_scale(
    map_size: float,
    coordinates: list[tuple[float, float, ...]],
    scale_mode: str,
    path_scale: float = 0.8,
) -> float:
    """Compute the horizontal scale factor for the terrain mesh."""
    min_lat = min(p[0] for p in coordinates)
    max_lat = max(p[0] for p in coordinates)
    min_lon = min(p[1] for p in coordinates)
    max_lon = max(p[1] for p in coordinates)

    x1, y1, _ = convert_to_neutral(min_lat, min_lon, 0)
    x2, y2, _ = convert_to_neutral(max_lat, max_lon, 0)

    width = abs(x2 - x1)
    height = abs(y2 - y1)
    maxer = max(width, height)

    if maxer == 0:
        return 1.0

    if scale_mode == "COORDINATES":
        return map_size / maxer
    elif scale_mode == "FACTOR":
        return (map_size * path_scale) / maxer
    else:  # SCALE
        return path_scale


def move_coordinates(
    lat: float, lon: float, distance_km: float, direction: str
) -> tuple[float, float]:
    """Displace a point by distance_km in a cardinal direction."""
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    d = direction.lower()
    if d == "n":
        lat_rad += distance_km / R
    elif d == "s":
        lat_rad -= distance_km / R
    elif d == "e":
        lon_rad += distance_km / (R * math.cos(lat_rad))
    elif d == "w":
        lon_rad -= distance_km / (R * math.cos(lat_rad))
    else:
        raise ValueError(f"Direction must be n/s/e/w, got {direction!r}")
    return math.degrees(lat_rad), math.degrees(lon_rad)


def bbox_for_track(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    padding_km: float = 2.0,
) -> tuple[float, float, float, float]:
    """Expand a bounding box by padding_km on each side."""
    lat_pad = padding_km / R * (180.0 / math.pi)
    mid_lat = (min_lat + max_lat) / 2
    # Clamp cos to avoid division by near-zero at polar latitudes (would produce globe-spanning bbox)
    cos_mid = max(math.cos(math.radians(mid_lat)), 1e-4)
    lon_pad = min(5.0, padding_km / (R * cos_mid) * (180.0 / math.pi))
    return (
        max(-90.0, min_lat - lat_pad),
        max(-180.0, min_lon - lon_pad),
        min(90.0, max_lat + lat_pad),
        min(180.0, max_lon + lon_pad),
    )


def separate_duplicate_xy(
    coordinates: list[list[float]], offset: float = 0.05
) -> list[list[float]]:
    """Slightly offset duplicate XYZ points to avoid degenerate geometry."""
    seen: set[tuple] = set()
    for point in coordinates:
        key = (point[0], point[1], point[2])
        if key in seen:
            point[2] += offset
            point[1] += offset
        else:
            seen.add(key)
    return coordinates
