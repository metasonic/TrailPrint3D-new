"""
OpenStreetMap / Overpass API fetcher — extracted from TrailPrint3D/utils/osm.py.
All bpy dependencies removed; config injected via OsmConfig.
Disk-based SHA-256 cache preserved.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class OsmConfig:
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    cache_dir: Path = Path("/app/.cache")
    disable_cache: bool = False
    cache_max_age_hours: int = 720
    api_retries: int = 5
    map_size_km: float = 50.0
    # Feature toggles
    water_ponds: bool = False
    water_small_rivers: bool = False
    water_big_rivers: bool = False
    roads_big: bool = False
    roads_med: bool = False
    roads_small: bool = False

    @property
    def osm_cache_dir(self) -> Path:
        d = self.cache_dir / "osm"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _make_cache_key(bbox: tuple, kind: str, config: OsmConfig) -> str:
    south, west, north, east = bbox
    payload: dict = {
        "bbox": [round(south, 7), round(west, 7), round(north, 7), round(east, 7)],
        "kind": kind,
    }
    if kind == "STREETS":
        payload["r"] = f"{config.roads_big}{config.roads_med}{config.roads_small}"
    if kind == "WATER":
        payload["w"] = f"{config.water_ponds}{config.water_small_rivers}{config.water_big_rivers}"
    data = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def _bbox_header(s: float, w: float, n: float, e: float) -> str:
    return f"[out:json][timeout:60][bbox:{s},{w},{n},{e}]"


def _build_query(bbox: tuple, kind: str, config: OsmConfig) -> str:
    s, w, n, e = bbox

    if kind == "WATER":
        parts = []
        if config.water_ponds:
            parts.append("(way[natural=water];relation[natural=water];);")
        if config.water_small_rivers:
            parts.append("(way[waterway~'stream|canal|ditch'];);")
        if config.water_big_rivers:
            parts.append("(way[waterway=river][wikidata];relation[waterway=river][wikidata];);")
        body = "\n".join(parts) if parts else "(way[natural=water];);"
        return f"{_bbox_header(s,w,n,e)}\n({body}\n);\nout body;\n>;\nout skel qt;"

    elif kind == "FOREST":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[landuse=forest];way[natural=wood];"
            "relation[landuse=forest];relation[natural=wood];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "CITY":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(relation[boundary=administrative][admin_level~'^[6-8]$'];"
            "way[boundary=administrative][admin_level~'^[6-8]$'];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "GREENSPACE":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[leisure~'park|garden|recreation_ground'];"
            "way[landuse~'grass|meadow|village_green'];"
            "relation[leisure~'park|garden'];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "FARMLAND":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[landuse~'farmland|farmyard'];relation[landuse~'farmland|farmyard'];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "GLACIER":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[natural=glacier];relation[natural=glacier];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "SCREE":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[natural=scree];relation[natural=scree];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "BUILDINGS":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[building];relation[building];);\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "STREETS":
        road_filters = []
        if config.roads_big:
            road_filters.append("way[highway~'motorway|primary|motorway_link|primary_link']")
        if config.roads_med:
            road_filters.append("way[highway~'secondary|tertiary|secondary_link|tertiary_link']")
        if config.roads_small:
            road_filters.append("way[highway~'residential|living_street|unclassified|service|footway']")
        if not road_filters:
            road_filters.append("way[highway~'motorway|primary']")
        body = ";".join(road_filters) + ";"
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            f"({body});\n"
            "out body;\n>;\nout skel qt;"
        )

    elif kind == "OCEAN":
        return (
            f"{_bbox_header(s,w,n,e)}\n"
            "(way[natural=coastline];);\n"
            "out body;\n>;\nout skel qt;"
        )

    raise ValueError(f"Unknown OSM kind: {kind!r}")


def fetch_osm_data(
    bbox: tuple[float, float, float, float],
    kind: str,
    config: OsmConfig,
) -> Optional[dict]:
    """Fetch OSM data for a bounding box, using the disk cache when fresh."""
    cache_key = _make_cache_key(bbox, kind, config)
    cache_path = config.osm_cache_dir / f"{cache_key}.json"

    if cache_path.exists() and not config.disable_cache:
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < config.cache_max_age_hours:
            try:
                return json.loads(cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt/partial cache file — fall through to re-fetch

    s, w, n, e = bbox
    s = max(-90.0, min(90.0, s))
    n = max(-90.0, min(90.0, n))
    w = max(-180.0, min(180.0, w))
    e = max(-180.0, min(180.0, e))

    query = _build_query((s, w, n, e), kind, config)

    for attempt in range(config.api_retries):
        try:
            resp = requests.post(
                config.overpass_url,
                data={"data": query},
                timeout=90,
            )
            resp.raise_for_status()
            data = resp.json()
            # Atomic write to avoid partial reads by concurrent requests
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.replace(cache_path)
            return data
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("OSM fetch attempt %d failed; retrying in %ds", attempt + 1, wait)
            time.sleep(wait)

    return None


def build_osm_nodes(data: dict) -> dict[int, tuple[float, float]]:
    """Build a node-id → (lat, lon) lookup from an Overpass response."""
    return {el["id"]: (el["lat"], el["lon"]) for el in data.get("elements", []) if el["type"] == "node"}


def extract_polygon_coords(
    element: dict,
    nodes: dict[int, tuple[float, float]],
) -> list[tuple[float, float]]:
    """Return a list of (lat, lon) pairs for a way element."""
    coords = []
    for nid in element.get("nodes", []):
        if nid in nodes:
            coords.append(nodes[nid])
    return coords
