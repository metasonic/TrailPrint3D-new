"""Unit tests for geospatial math utilities."""
import math
import pytest

from backend.pipeline.geo import (
    haversine,
    mercator_x,
    mercator_y,
    convert_to_world,
    convert_to_neutral,
    calculate_scale,
    move_coordinates,
    bbox_for_track,
)


def test_haversine_known_distance():
    # Paris → Berlin ≈ 878 km
    dist = haversine(48.8566, 2.3522, 52.5200, 13.4050)
    assert 870 < dist < 890


def test_haversine_zero():
    assert haversine(47.0, 8.0, 47.0, 8.0) == pytest.approx(0.0)


def test_mercator_x_increases_east():
    x1 = mercator_x(0.0)
    x2 = mercator_x(10.0)
    assert x2 > x1


def test_mercator_y_increases_north():
    y1 = mercator_y(0.0)
    y2 = mercator_y(45.0)
    assert y2 > y1


def test_convert_to_world_elevation_scale():
    _, _, z1 = convert_to_world(47.0, 8.0, 1000.0, scale_elevation=1.0)
    _, _, z2 = convert_to_world(47.0, 8.0, 1000.0, scale_elevation=2.0)
    assert z2 == pytest.approx(z1 * 2, rel=1e-6)


def test_calculate_scale_factor_mode():
    # A set of points spanning roughly 1 degree lat/lon
    coords = [(47.0, 8.0, 0, None), (48.0, 9.0, 0, None)]
    scale = calculate_scale(100.0, coords, "FACTOR", path_scale=0.8)
    assert scale > 0


def test_move_coordinates_north():
    lat, lon = move_coordinates(47.0, 8.0, 10.0, "n")
    assert lat > 47.0
    assert abs(lon - 8.0) < 1e-9


def test_move_coordinates_east():
    lat, lon = move_coordinates(47.0, 8.0, 10.0, "e")
    assert lon > 8.0
    assert abs(lat - 47.0) < 1e-9


def test_bbox_for_track_expands():
    s, w, n, e = bbox_for_track(47.0, 8.0, 48.0, 9.0, padding_km=10.0)
    assert s < 47.0
    assert w < 8.0
    assert n > 48.0
    assert e > 9.0
