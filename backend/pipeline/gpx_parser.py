"""
GPX / IGC parser — extracted from TrailPrint3D/utils/io_gpx.py.
All bpy dependencies removed; returns plain Python data structures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import logging as _log
    _log.getLogger(__name__).warning(
        "defusedxml not installed — falling back to stdlib xml.etree.ElementTree "
        "which is vulnerable to XML bomb (billion laughs) attacks. "
        "Install defusedxml for security: pip install defusedxml"
    )
    import xml.etree.ElementTree as ET  # type: ignore[no-redef]


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
    date: Optional[str] = None


def _parse_points(points: list, point_type: str) -> Segment:
    segcoords: Segment = []
    for pt in points:
        lat_str = pt.get("lat")
        lon_str = pt.get("lon")
        if lat_str is None or lon_str is None:
            continue  # skip malformed points missing required coordinates
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, TypeError):
            continue
        ele = None
        time_el = None
        for c in pt:
            tag = c.tag.split("}")[-1]
            if tag == "ele":
                ele = c
            elif tag == "time":
                time_el = c
        try:
            elevation = float(ele.text) if ele is not None and ele.text else 0.0
        except (ValueError, TypeError):
            elevation = 0.0
        try:
            timestamp = (
                datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
                if time_el is not None and time_el.text
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
    flight_date: Optional[_date] = None

    with open(str(filepath), "r", encoding="latin-1") as f:
        lines = f.readlines()

    # Parse HFDTE header to get the actual flight date.
    # Supports both classic (HFDTE240513) and newer (HFDTEDATE:240513,01) formats.
    for line in lines:
        line = line.strip()
        if line.startswith("HFDTE"):
            try:
                rest = line[5:].lstrip(": ")
                # HFDTEDATE:DDMMYY,NN — drop everything after the comma
                d = rest.split(",")[0].strip()[:6]
                flight_date = _date(
                    2000 + int(d[4:6]), int(d[2:4]), int(d[0:2])
                )
            except (ValueError, IndexError):
                pass
            break

    today = datetime.now(timezone.utc).date()
    base_date = flight_date or today

    prev_secs: Optional[int] = None
    for line in lines:
        if not line.startswith("B"):
            continue
        try:
            time_str = line[1:7]
            hours = int(time_str[0:2])
            minutes = int(time_str[2:4])
            seconds = int(time_str[4:6])

            # Detect midnight rollover: if time jumps backwards by more than 1 hour,
            # the flight crossed midnight → advance base_date by one day.
            current_secs = hours * 3600 + minutes * 60 + seconds
            if prev_secs is not None and current_secs < prev_secs - 3600:
                base_date = (datetime(base_date.year, base_date.month, base_date.day)
                             + timedelta(days=1)).date()
            prev_secs = current_secs

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

            # Validity flag: 'A' = 3-D fix, 'V' = 2-D / invalid.
            # Skip records with unrecognised flag characters (malformed B records).
            if line[24:25] not in ("A", "V"):
                continue

            gps_alt = int(line[30:35])
            timestamp = datetime(base_date.year, base_date.month, base_date.day,
                                 hours, minutes, seconds, tzinfo=timezone.utc)
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
        return TrackStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, date=None)

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    elevs = [p[2] for p in points]

    length_km = 0.0
    for i in range(1, len(points)):
        length_km += haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

    elevation_gain = sum(
        max(0.0, elevs[i] - elevs[i - 1]) for i in range(1, len(elevs))
    )

    date: Optional[str] = None
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
