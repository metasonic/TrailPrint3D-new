"""
Elevation data fetching — extracted from TrailPrint3D/utils/elevation.py.
All bpy dependencies removed; config is injected via ElevationConfig.
Supports: Terrain-Tiles (Terrarium/AWS), OpenTopoData, Open-Elevation, OpenTopography.
"""
from __future__ import annotations

import io
import json
import logging
import math
import struct
import threading
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ElevationConfig:
    api: str = "TERRAIN-TILES"
    dataset: str = "aster30m"
    opentopography_dataset: str = "SRTMGL1"
    opentopodata_url: str = "https://api.opentopodata.org/v1/"
    opentopography_api_key: str = ""
    cache_dir: Path = Path("/app/.cache")
    disable_cache: bool = False
    num_subdivisions: int = 4
    elevation_cache_size: int = 50000
    # bbox needed for terrain-tiles zoom calculation
    min_lat: float = 0.0
    min_lon: float = 0.0
    max_lat: float = 0.0
    max_lon: float = 0.0

    @property
    def elevation_cache_file(self) -> Path:
        return self.cache_dir / "elevation" / "cache.json"

    @property
    def terrarium_cache_dir(self) -> Path:
        d = self.cache_dir / "tiles"
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------------------------------------------------------------------------
# In-memory + disk elevation cache — protected by a lock for thread safety
# under asyncio.to_thread concurrency.
# ---------------------------------------------------------------------------

_cache: dict[str, float] = {}
_cache_lock = threading.Lock()
_cache_loaded = False


def _load_cache(config: ElevationConfig) -> None:
    global _cache, _cache_loaded
    p = config.elevation_cache_file
    with _cache_lock:
        if _cache_loaded:
            return
        if p.exists():
            try:
                _cache = json.loads(p.read_text())
            except Exception:
                _cache = {}
        else:
            _cache = {}
        _cache_loaded = True


def _save_cache(config: ElevationConfig) -> None:
    p = config.elevation_cache_file
    p.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        max_size = config.elevation_cache_size
        if max_size <= 0:
            _cache.clear()
        elif len(_cache) > max_size:
            keys = list(_cache.keys())
            for k in keys[:-max_size]:
                del _cache[k]
        snapshot = dict(_cache)
    # Atomic write: write to temp file then replace to avoid partial reads
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot))
        tmp.replace(p)
    except Exception:
        pass


def _cache_key(lat: float, lon: float, api_type: str = "tt") -> str:
    return f"{lat:.5f}_{lon:.5f}_{api_type}"


def _get_cached(lat: float, lon: float, api_type: str = "tt") -> Optional[float]:
    with _cache_lock:
        if not _cache_loaded:
            return None
        return _cache.get(_cache_key(lat, lon, api_type))


def _set_cached(lat: float, lon: float, elevation: float, api_type: str = "tt") -> None:
    with _cache_lock:
        _cache[_cache_key(lat, lon, api_type)] = elevation


# ---------------------------------------------------------------------------
# Terrain-Tiles (Terrarium / AWS S3) — fastest, no API key required
# ---------------------------------------------------------------------------

def _lonlat_to_tilexy(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lon = max(-180.0, min(180.0, lon))
    lat = max(-85.051129, min(85.051129, lat))  # Web Mercator valid range
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    # Clamp to valid tile range [0, 2^zoom - 1] — lon=180 produces x=2^zoom (out of bounds)
    max_tile = int(n) - 1
    return min(x, max_tile), min(y, max_tile)


def _lonlat_to_pixelxy(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lon = max(-180.0, min(180.0, lon))
    lat = max(-85.051129, min(85.051129, lat))
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    px = (lon + 180.0) / 360.0 * n * 256
    py = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n * 256
    return int(px % 256), int(py % 256)


def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    return c


def _parse_png_rgb(png_bytes: bytes) -> list[list[tuple[int, int, int]]]:
    """Decode an 8-bit RGB or RGBA PNG without external libraries.

    Accepts color_type 2 (RGB) and color_type 6 (RGBA — alpha is discarded).
    Some CDN-cached terrain tiles are served as RGBA; rejecting them would
    silently produce zero-elevation grids.
    """
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a valid PNG file (bad magic bytes)")
    offset = 8
    width = height = 0
    color_type = 2
    idat = b""
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk = png_bytes[offset + 4 : offset + 8]
        data = png_bytes[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
            if bit_depth != 8 or color_type not in (2, 6):
                raise ValueError(
                    f"Unsupported PNG format: bit_depth={bit_depth}, color_type={color_type}"
                    " (expected 8-bit RGB or RGBA)"
                )
            # Byte 12 of IHDR data is the interlace method; Adam7-interlaced tiles
            # have a completely different data layout and would silently produce
            # garbage elevation values if decoded as non-interlaced.
            if len(data) > 12 and data[12] != 0:
                raise ValueError(f"Interlaced PNG tiles are not supported (interlace={data[12]})")
        elif chunk == b"IDAT":
            idat += data
        elif chunk == b"IEND":
            break
    # 2MB cap prevents decompression of maliciously crafted tiles (zip bomb)
    _obj = zlib.decompressobj()
    raw = _obj.decompress(idat, max_length=2 * 1024 * 1024)
    if _obj.unconsumed_tail:
        raise ValueError("PNG IDAT data exceeds decompression size limit")
    # RGB = 3 bytes/pixel, RGBA = 4 bytes/pixel
    n_ch = 3 if color_type == 2 else 4
    stride = n_ch * width
    result = []
    prev = bytearray(stride)
    for row_idx in range(height):
        i = row_idx * (stride + 1)
        ftype = raw[i]
        scan = bytearray(raw[i + 1 : i + 1 + stride])
        recon = bytearray(stride)
        if ftype == 0:
            recon[:] = scan
        elif ftype == 1:
            for j in range(stride):
                recon[j] = (scan[j] + (recon[j - n_ch] if j >= n_ch else 0)) & 0xFF
        elif ftype == 2:
            for j in range(stride):
                recon[j] = (scan[j] + prev[j]) & 0xFF
        elif ftype == 3:
            for j in range(stride):
                left = recon[j - n_ch] if j >= n_ch else 0
                recon[j] = (scan[j] + (left + prev[j]) // 2) & 0xFF
        elif ftype == 4:
            for j in range(stride):
                a = recon[j - n_ch] if j >= n_ch else 0
                b_val = prev[j]
                c = prev[j - n_ch] if j >= n_ch else 0
                recon[j] = (scan[j] + _paeth_predictor(a, b_val, c)) & 0xFF
        else:
            raise ValueError(f"Unknown PNG filter type {ftype} in row {row_idx}")
        # Extract only R,G,B — skip alpha if present
        result.append([(recon[j], recon[j + 1], recon[j + 2]) for j in range(0, stride, n_ch)])
        prev = recon
    return result


def _terrarium_to_elevation(r: int, g: int, b: int) -> float:
    return (r * 256 + g + b / 256) - 32768


def _fetch_tile(zoom: int, x: int, y: int, config: ElevationConfig) -> bytes:
    path = config.terrarium_cache_dir / f"{zoom}_{x}_{y}.png"
    if path.exists():
        return path.read_bytes()
    url = f"https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{zoom}/{x}/{y}.png"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Sanitize: strip the URL (which contains no secrets, but keeps messages clean)
        raise requests.HTTPError(
            f"Terrain tile fetch failed: HTTP {e.response.status_code}"
        ) from None
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(path)  # atomic rename; safe under concurrent requests
    return resp.content


def get_elevation_terrain_tiles(
    coords: list[tuple[float, float]],
    config: ElevationConfig,
    progress_cb=None,
) -> list[float]:
    from .geo import haversine

    min_lat, min_lon, max_lat, max_lon = (
        config.min_lat, config.min_lon, config.max_lat, config.max_lon,
    )
    realdist = max(
        haversine(min_lat, min_lon, min_lat, max_lon) * 1000,
        haversine(max_lat, min_lon, max_lat, max_lon) * 1000,
    )
    hor_verts = 1 + 2 ** (config.num_subdivisions + 1)
    # Intervals between vertices, not vertex count
    vert_dist = realdist / (hor_verts - 1) if hor_verts > 1 else realdist

    lat_center = (min_lat + max_lat) / 2
    cos_lat = math.cos(math.radians(lat_center))
    zoom = 2
    # Tile resolution at the track's latitude: 156543 m/px at zoom 0, halved per zoom level
    tile_m_per_px = 156543.0 * cos_lat / (2 ** zoom)
    while tile_m_per_px > vert_dist and zoom < 15:
        zoom += 1
        tile_m_per_px /= 2

    tile_cache: dict[tuple, list] = {}
    elevations = [0.0] * len(coords)
    tile_map: dict[tuple, list[tuple[int, float, float]]] = {}
    for idx, (lat, lon) in enumerate(coords):
        key = _lonlat_to_tilexy(lon, lat, zoom)
        tile_map.setdefault(key, []).append((idx, lat, lon))

    total = len(tile_map)
    for i, ((tx, ty), entries) in enumerate(tile_map.items()):
        if (tx, ty) not in tile_cache:
            raw = _fetch_tile(zoom, tx, ty, config)
            try:
                tile_cache[(tx, ty)] = _parse_png_rgb(raw)
            except Exception:
                logger.warning("Malformed terrain tile %d/%d/%d; using zero elevation", zoom, tx, ty)
                tile_cache[(tx, ty)] = [[(0, 0, 0)] * 256 for _ in range(256)]
        rgb_grid = tile_cache[(tx, ty)]
        for idx, lat, lon in entries:
            px, py = _lonlat_to_pixelxy(lon, lat, zoom)
            r, g, b = rgb_grid[min(py, 255)][min(px, 255)]
            elevations[idx] = _terrarium_to_elevation(r, g, b)
        if progress_cb:
            progress_cb(int((i + 1) / total * 100))

    return elevations


# ---------------------------------------------------------------------------
# OpenTopoData
# ---------------------------------------------------------------------------

def get_elevation_opentopodata(
    coords: list[tuple[float, float]],
    config: ElevationConfig,
    progress_cb=None,
) -> list[float]:
    _load_cache(config)

    to_fetch = []
    indices = []
    elevations = [0.0] * len(coords)

    for i, (lat, lon) in enumerate(coords):
        cached = _get_cached(lat, lon, "otd")
        if cached is not None and not config.disable_cache:
            elevations[i] = cached
        else:
            to_fetch.append((lat, lon))
            indices.append(i)

    batch_size = 10
    total = len(to_fetch)
    url_base = config.opentopodata_url.rstrip("/") + f"/{config.dataset}"

    for i in range(0, total, batch_size):
        batch = to_fetch[i : i + batch_size]
        query = "|".join(f"{lat},{lon}" for lat, lon in batch)
        t0 = time.monotonic()
        resp = requests.get(f"{url_base}?locations={query}", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            logger.warning("OpenTopoData returned no results for batch at index %d", i)
        for o, result in enumerate(results):
            if o >= len(batch):
                break  # guard against API returning more results than requested
            elev = result.get("elevation") or 0.0
            _set_cached(batch[o][0], batch[o][1], elev, "otd")
            elevations[indices[i + o]] = elev
        if progress_cb:
            progress_cb(int(min((i + len(batch)) / total * 100, 100)))
        elapsed = time.monotonic() - t0
        if i + batch_size < total and elapsed < 1.3:
            time.sleep(1.3 - elapsed)

    _save_cache(config)
    return elevations


# ---------------------------------------------------------------------------
# Open-Elevation
# ---------------------------------------------------------------------------

def get_elevation_open_elevation(
    coords: list[tuple[float, float]],
    config: ElevationConfig,
    progress_cb=None,
) -> list[float]:
    # Pre-allocate so partial API responses don't cause reshape errors
    elevations = [0.0] * len(coords)
    batch_size = 1000
    total = len(coords)

    for i in range(0, total, batch_size):
        batch = coords[i : i + batch_size]
        payload = {"locations": [{"latitude": lat, "longitude": lon} for lat, lon in batch]}
        t0 = time.monotonic()
        resp = requests.post(
            "https://api.open-elevation.com/api/v1/lookup",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        for o, result in enumerate(data.get("results", [])):
            if i + o < len(elevations):
                elevations[i + o] = float(result.get("elevation") or 0.0)
        if progress_cb:
            progress_cb(int(min((i + len(batch)) / total * 100, 100)))
        elapsed = time.monotonic() - t0
        if elapsed < 2:
            time.sleep(2 - elapsed)

    return elevations


# ---------------------------------------------------------------------------
# OpenTopography
# ---------------------------------------------------------------------------

def get_elevation_opentopography(
    coords: list[tuple[float, float]],
    config: ElevationConfig,
    progress_cb=None,
) -> list[float]:
    if not config.opentopography_api_key:
        raise ValueError("OPENTOPOGRAPHY_API_KEY is required for the OpenTopography API")

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    south, north = min(lats), max(lats)
    west, east = min(lons), max(lons)

    params = {
        "demtype": config.opentopography_dataset,
        "south": south, "north": north,
        "west": west, "east": east,
        "outputFormat": "GTiff",
        "API_Key": config.opentopography_api_key,
    }
    try:
        resp = requests.get(
            "https://portal.opentopography.org/API/globaldem",
            params=params,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Sanitize error: the URL contains the API key as a query parameter
        raise requests.HTTPError(
            f"OpenTopography API request failed: HTTP {e.response.status_code}"
        ) from None

    # Parse GeoTIFF via rasterio if available, otherwise fall back to OpenTopoData
    try:
        import rasterio
        import numpy as np
        with rasterio.open(io.BytesIO(resp.content)) as src:
            band = src.read(1)
            elevations = []
            for lat, lon in coords:
                row, col = src.index(lon, lat)
                row = max(0, min(row, band.shape[0] - 1))
                col = max(0, min(col, band.shape[1] - 1))
                elevations.append(float(band[row, col]))
        return elevations
    except ImportError:
        # Fall back to OpenTopoData with SRTM30m
        fallback = ElevationConfig(
            api="OPENTOPODATA",
            dataset="srtm30m",
            opentopodata_url=config.opentopodata_url,
            cache_dir=config.cache_dir,
        )
        return get_elevation_opentopodata(coords, fallback, progress_cb)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def get_elevations(
    coords: list[tuple[float, float]],
    config: ElevationConfig,
    progress_cb=None,
) -> list[float]:
    """Fetch elevations for a list of (lat, lon) pairs using the configured API."""
    api = config.api.upper()
    if api == "TERRAIN-TILES":
        return get_elevation_terrain_tiles(coords, config, progress_cb)
    elif api == "OPENTOPODATA":
        return get_elevation_opentopodata(coords, config, progress_cb)
    elif api == "OPEN-ELEVATION":
        return get_elevation_open_elevation(coords, config, progress_cb)
    elif api == "OPENTOPOGRAPHY":
        return get_elevation_opentopography(coords, config, progress_cb)
    else:
        raise ValueError(f"Unknown elevation API: {config.api!r}")
