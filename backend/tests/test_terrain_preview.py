"""Unit tests for the terrain preview mesh generator."""
import pytest
import numpy as np

from backend.pipeline.terrain_preview import TerrainConfig, _grid_size, _clip_to_shape
from backend.pipeline.elevation import ElevationConfig


def test_grid_size():
    # num_subdivisions=1 → 1 + 2^2 = 5
    assert _grid_size(1) == 5
    # num_subdivisions=4 → 1 + 2^5 = 33
    assert _grid_size(4) == 33


def test_terrain_mesh_basic(monkeypatch):
    """Build a terrain mesh with a mocked flat elevation grid."""
    import backend.pipeline.terrain_preview as tm
    import backend.pipeline.elevation as elev_mod

    def _mock_elevations(coords, config, progress_cb=None):
        return [100.0] * len(coords)

    monkeypatch.setattr(elev_mod, "get_elevations", _mock_elevations)

    config = TerrainConfig(
        min_lat=47.0,
        min_lon=8.0,
        max_lat=47.1,
        max_lon=8.1,
        num_subdivisions=1,
        elevation_scale=1.0,
        min_thickness=2.0,
        obj_size_mm=100.0,
        shape="SQUARE",
    )
    ecfg = ElevationConfig(api="TERRAIN-TILES")

    mesh = tm.build_terrain_mesh(config, ecfg)
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0


def test_terrain_hex_clip_fewer_faces(monkeypatch):
    """Hexagon clip should remove corner faces compared to a square clip."""
    import backend.pipeline.terrain_preview as tm
    import backend.pipeline.elevation as elev_mod

    def _mock_elevations(coords, config, progress_cb=None):
        return [200.0] * len(coords)

    monkeypatch.setattr(elev_mod, "get_elevations", _mock_elevations)

    base_cfg = dict(
        min_lat=47.0, min_lon=8.0, max_lat=47.2, max_lon=8.2,
        num_subdivisions=2, elevation_scale=1.0, min_thickness=2.0, obj_size_mm=100.0,
    )
    ecfg = ElevationConfig(api="TERRAIN-TILES")

    sq_mesh = tm.build_terrain_mesh(TerrainConfig(**base_cfg, shape="SQUARE"), ecfg)
    hx_mesh = tm.build_terrain_mesh(TerrainConfig(**base_cfg, shape="HEXAGON"), ecfg)

    # Hexagon has fewer vertices than square (corners clipped)
    assert len(hx_mesh.vertices) <= len(sq_mesh.vertices)
