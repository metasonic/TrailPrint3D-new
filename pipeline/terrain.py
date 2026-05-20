"""DEM acquisition (with a thin bbox-keyed cache), reprojection, and terrain mesh.

Brief constraint: AWS Open Data SRTM 30 m via the `elevation` Python package.
Cache strategy (locked in docs/phase2_pipeline_design.md): bbox rounded to 4
decimal degrees, GeoTIFFs stored under ELEVATION_CACHE_DIR.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import elevation
import numpy as np
import rasterio
import trimesh
from pyproj import CRS, Transformer
from rasterio.transform import Affine

from backend.app.settings import settings
from pipeline.track import BBoxWGS84

logger = logging.getLogger(__name__)


def _cache_path(bbox: BBoxWGS84) -> Path:
    """Stable on-disk key for a bbox. Rounds to 4 decimal degrees (~11 m at the equator)."""
    lon_min, lat_min, lon_max, lat_max = (round(v, 4) for v in bbox)
    name = f"dem_{lon_min}_{lat_min}_{lon_max}_{lat_max}.tif"
    return settings.elevation_cache_dir / name


def _budget_mb(bbox: BBoxWGS84) -> float:
    """Rough estimate of the GeoTIFF size for this bbox at SRTM 30 m, 16-bit."""
    lon_min, lat_min, lon_max, lat_max = bbox
    # SRTM 30 m: 3600 samples per degree of lat; lon samples scaled by cos(lat)
    mid_lat = math.radians(0.5 * (lat_min + lat_max))
    rows = (lat_max - lat_min) * 3600
    cols = (lon_max - lon_min) * 3600 * max(math.cos(mid_lat), 0.1)
    return rows * cols * 2 / (1024 * 1024)


def fetch_dem(bbox: BBoxWGS84) -> tuple[np.ndarray, Affine, CRS, bool]:
    """Download (or read from cache) an SRTM 30 m DEM for the bbox.

    Returns (elevation_array_m, geotransform, src_crs, cache_hit). The
    geotransform maps array (col, row) → (lon, lat) in src_crs (always EPSG:4326
    for SRTM).
    """
    cache_path = _cache_path(bbox)
    cache_hit = cache_path.exists()
    if not cache_hit:
        budget = _budget_mb(bbox)
        if budget > settings.max_dem_download_mb:
            raise RuntimeError(
                f"DEM for this bbox would be ~{budget:.1f} MB, exceeds "
                f"MAX_DEM_DOWNLOAD_MB={settings.max_dem_download_mb}"
            )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        product = "SRTM1" if settings.dem_resolution == 30 else "SRTM3"
        logger.info("downloading DEM bbox=%s product=%s -> %s", bbox, product, cache_path)
        elevation.clip(bounds=bbox, output=str(cache_path), product=product)
    with rasterio.open(cache_path) as src:
        array = src.read(1).astype(np.float64)
        transform = src.transform
        src_crs = CRS.from_user_input(src.crs)
    # SRTM no-data is -32768; clamp to 0 so we don't get oceans below the floor
    array = np.where(array < -1000, 0.0, array)
    return array, transform, src_crs, cache_hit


def build_terrain_mesh(
    dem: np.ndarray,
    transform: Affine,
    src_crs: CRS,
    target_crs: CRS,
    subdivisions: int,
    scale: float,
    base_thickness: float,
    model_size_mm: float,
) -> trimesh.Trimesh:
    """Reproject the DEM into target_crs, build a watertight terrain plate.

    Args:
        dem: 2D elevation array in metres.
        transform: rasterio Affine; maps array (col, row) → src_crs coords.
        src_crs: input CRS (EPSG:4326 for SRTM).
        target_crs: output CRS (a local UTM zone for metric XY).
        subdivisions: downsampling stride; 1 = full DEM resolution, 4 = every 4th sample.
        scale: vertical exaggeration factor applied to elevation.
        base_thickness: thickness of the flat base added below min(z), in pre-scale meters
            (will be scaled to mm alongside everything else).
        model_size_mm: longest XY edge of the final mesh, in millimetres.

    The resulting mesh is centred at XY=(0,0) with its base at Z=0. The same
    XY scale factor is recorded in `mesh.metadata` so the track tube can match.
    """
    # 1. Downsample
    stride = max(1, subdivisions)
    sampled = dem[::stride, ::stride]
    rows, cols = sampled.shape
    if rows < 2 or cols < 2:
        raise ValueError("DEM too small after subdivision")

    # 2. Generate (lon, lat) for each sampled pixel via the source transform
    col_ix, row_ix = np.meshgrid(np.arange(cols), np.arange(rows))
    src_x, src_y = rasterio.transform.xy(transform, row_ix * stride, col_ix * stride)
    src_x = np.asarray(src_x, dtype=np.float64)
    src_y = np.asarray(src_y, dtype=np.float64)

    # 3. Reproject to UTM
    transformer = Transformer.from_crs(src_crs, target_crs, always_xy=True)
    east, north = transformer.transform(src_x, src_y)

    # 4. Apply vertical scale
    z = sampled * scale

    # 5. Build top-surface vertices and a regular grid triangulation
    top = np.stack([east.ravel(), north.ravel(), z.ravel()], axis=1)
    faces_top = _grid_faces(rows, cols, flip=False)

    # 6. Bottom plane at min(z) - base_thickness, same XY
    z_bottom = float(z.min()) - base_thickness
    bottom = top.copy()
    bottom[:, 2] = z_bottom
    faces_bottom = _grid_faces(rows, cols, flip=True) + len(top)

    # 7. Side walls: stitch the four boundary edges between top and bottom rings
    n = len(top)
    side_faces = _side_wall_faces(rows, cols, top_offset=0, bottom_offset=n)

    vertices = np.vstack([top, bottom])
    faces = np.vstack([faces_top, faces_bottom, side_faces])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    # Our hand-rolled winding is globally inverted relative to trimesh's outward
    # convention; fix_normals reorients faces so outward normals point outward.
    mesh.fix_normals()
    if not mesh.is_volume:
        raise RuntimeError("terrain mesh is not a valid volume after construction")

    # 8. Centre at (0,0) in XY, base at Z=0
    centre_x = float(0.5 * (mesh.bounds[0, 0] + mesh.bounds[1, 0]))
    centre_y = float(0.5 * (mesh.bounds[0, 1] + mesh.bounds[1, 1]))
    mesh.apply_translation(np.array([-centre_x, -centre_y, -float(mesh.bounds[0, 2])]))

    # 9. Scale uniformly so longest XY edge = model_size_mm
    xy_extent = max(mesh.extents[0], mesh.extents[1])
    if xy_extent <= 0:
        raise RuntimeError("Terrain mesh has zero XY extent")
    factor = model_size_mm / xy_extent
    mesh.apply_scale(float(factor))  # type: ignore[no-untyped-call]

    # Record metadata the track extruder needs
    mesh.metadata["xy_scale"] = factor
    mesh.metadata["z_scale"] = factor * scale  # combined factor for the same elevation samples
    mesh.metadata["utm_centre"] = (centre_x, centre_y)
    mesh.metadata["centre_x"] = 0.0  # already centred
    mesh.metadata["centre_y"] = 0.0
    return mesh


def _grid_faces(rows: int, cols: int, flip: bool) -> np.ndarray:
    """Triangle indices for a regular (rows × cols) grid.

    flip=True swaps winding so the surface normal points the other way (used
    for the bottom face so it points downward and the mesh stays watertight).
    """
    faces: list[tuple[int, int, int]] = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = r * cols + c
            b = r * cols + c + 1
            d = (r + 1) * cols + c
            e = (r + 1) * cols + c + 1
            if flip:
                faces.append((a, d, b))
                faces.append((b, d, e))
            else:
                faces.append((a, b, d))
                faces.append((b, e, d))
    return np.asarray(faces, dtype=np.int64)


def _side_wall_faces(rows: int, cols: int, top_offset: int, bottom_offset: int) -> np.ndarray:
    """Quad strips around the four edges between the top and bottom grids."""
    faces: list[tuple[int, int, int]] = []

    def add_quad(a_top: int, b_top: int) -> None:
        a_bot = a_top - top_offset + bottom_offset
        b_bot = b_top - top_offset + bottom_offset
        faces.append((a_top, b_top, b_bot))
        faces.append((a_top, b_bot, a_bot))

    # top row (r=0)
    for c in range(cols - 1):
        add_quad(top_offset + c + 1, top_offset + c)
    # bottom row (r=rows-1)
    last = (rows - 1) * cols
    for c in range(cols - 1):
        add_quad(top_offset + last + c, top_offset + last + c + 1)
    # left column (c=0)
    for r in range(rows - 1):
        add_quad(top_offset + r * cols, top_offset + (r + 1) * cols)
    # right column (c=cols-1)
    for r in range(rows - 1):
        add_quad(top_offset + (r + 1) * cols + (cols - 1), top_offset + r * cols + (cols - 1))
    return np.asarray(faces, dtype=np.int64)
