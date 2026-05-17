"""
GPX / IGC parser — extracted from TrailPrint3D/utils/io_gpx.py.
All bpy dependencies removed; returns plain Python data structures.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


TrackPoint = tuple[float, float, float, Optional[datetime]]  # lat, lon, elev, time
Segment = list[TrackPoint]


@dataclass
class TrackStats:
    point_count: int
    length_km: float
    elevation_gain_m: float
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    date: str = ""


def _parse_points(points: list, point_type: str) -> Segment:
    segcoords: Segment = []
    for pt in points:
        lat = float(pt.get("lat"))
        lon = float(pt.get("lon"))
        ele = None
        time_el = None
        for c in pt:
            tag = c.tag.split("}")[-1]
            if tag == "ele":
                ele = c
            elif tag == "time":
                time_el = c
        elevation = float(ele.text) if ele is not None else 0.0
        try:
            timestamp = (
                datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
                if time_el is not None
                else None
            )
        except Exception:
            timestamp = None
        segcoords.append((lat, lon, elevation, timestamp))
    return segcoords


def read_gpx(filepath: str | Path) -> list[Segment]:
    """
    Parse a GPX file; supports GPX 1.0/1.1, trk/rte, namespaced and bare.
    Returns a list of segments (each segment is a list of TrackPoints).
    """
    tree = ET.parse(str(filepath))
    root = tree.getroot()
    segmentlist: list[Segment] = []

    def strip_ns(tag: str) -> str:
        return tag.split("}")[-1]

    def findall_any(elem, names):
        return [e for e in elem.iter() if strip_ns(e.tag) in names]

    trksegs = findall_any(root, ["trkseg"])
    if trksegs:
        for seg in trksegs:
            pts = [p for p in seg if strip_ns(p.tag) == "trkpt"]
            if pts:
                segmentlist.append(_parse_points(pts, "TRKPT"))

    routes = findall_any(root, ["rte"])
    for rte in routes:
        pts = [p for p in rte if strip_ns(p.tag) == "rtept"]
        if pts:
            segmentlist.append(_parse_points(pts, "RTEPT"))

    if not segmentlist:
        pts = findall_any(root, ["trkpt", "rtept"])
        if pts:
            segmentlist.append(_parse_points(pts, "POINT"))

    return segmentlist


def read_igc(filepath: str | Path) -> list[Segment]:
    """Parse an IGC flight log file."""
    coordinates: Segment = []
    with open(str(filepath), "r") as f:
        for line in f:
            if not line.startswith("B"):
                continue
            try:
                time_str = line[1:7]
                hours = int(time_str[0:2])
                minutes = int(time_str[2:4])
                seconds = int(time_str[4:6])

                lat_str = line[7:15]
                lat_deg = int(lat_str[0:2])
                lat_min = int(lat_str[2:4])
                lat_min_frac = int(lat_str[4:7]) / 1000.0
                lat = lat_deg + (lat_min + lat_min_frac) / 60.0
                if lat_str[7] == "S":
                    lat = -lat

                lon_str = line[15:24]
                lon_deg = int(lon_str[0:3])
                lon_min = int(lon_str[3:5])
                lon_min_frac = int(lon_str[5:8]) / 1000.0
                lon = lon_deg + (lon_min + lon_min_frac) / 60.0
                if lon_str[8] == "W":
                    lon = -lon

                gps_alt = int(line[30:35])
                now = datetime.now()
                timestamp = datetime(now.year, now.month, now.day, hours, minutes, seconds)
                coordinates.append((lat, lon, float(gps_alt), timestamp))
            except (ValueError, IndexError):
                continue
    return [coordinates]


def read_track_file(filepath: str | Path) -> list[Segment]:
    """Auto-detect GPX or IGC and parse accordingly."""
    path = Path(filepath)
    ext = path.suffix.lower()
    if ext == ".gpx":
        return read_gpx(path)
    elif ext == ".igc":
        return read_igc(path)
    raise ValueError(f"Unsupported track format: {ext!r}. Use .gpx or .igc")


def flatten_segments(segments: list[Segment]) -> list[TrackPoint]:
    return [pt for seg in segments for pt in seg]


def compute_track_stats(segments: list[Segment]) -> TrackStats:
    from .geo import haversine

    points = flatten_segments(segments)
    if not points:
        return TrackStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    elevs = [p[2] for p in points]

    length_km = 0.0
    for i in range(1, len(points)):
        length_km += haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

    elevation_gain = sum(
        max(0.0, elevs[i] - elevs[i - 1]) for i in range(1, len(elevs))
    )

    date = ""
    if points[0][3] is not None:
        try:
            date = str(points[0][3].date())
        except Exception:
            pass

    return TrackStats(
        point_count=len(points),
        length_km=round(length_km, 3),
        elevation_gain_m=round(elevation_gain, 1),
        min_lat=min(lats),
        max_lat=max(lats),
        min_lon=min(lons),
        max_lon=max(lons),
        date=date,
    )
