"""Unit tests for the GPX parser pipeline module."""
import os
import tempfile
from pathlib import Path

import pytest

from backend.pipeline.gpx_parser import (
    read_gpx,
    read_igc,
    compute_track_stats,
    flatten_segments,
)

SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <trkseg>
      <trkpt lat="47.5" lon="8.5"><ele>400</ele><time>2024-06-01T08:00:00Z</time></trkpt>
      <trkpt lat="47.51" lon="8.51"><ele>420</ele><time>2024-06-01T08:10:00Z</time></trkpt>
      <trkpt lat="47.52" lon="8.52"><ele>410</ele><time>2024-06-01T08:20:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>"""


def _write_gpx(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w")
    f.write(content)
    f.close()
    return Path(f.name)


def test_read_gpx_returns_segments():
    path = _write_gpx(SAMPLE_GPX)
    try:
        segs = read_gpx(path)
        assert len(segs) == 1
        assert len(segs[0]) == 3
    finally:
        path.unlink()


def test_track_point_fields():
    path = _write_gpx(SAMPLE_GPX)
    try:
        segs = read_gpx(path)
        pt = segs[0][0]
        lat, lon, elev, ts = pt
        assert abs(lat - 47.5) < 1e-9
        assert abs(lon - 8.5) < 1e-9
        assert abs(elev - 400.0) < 1e-9
        assert ts is not None
    finally:
        path.unlink()


def test_compute_track_stats():
    path = _write_gpx(SAMPLE_GPX)
    try:
        segs = read_gpx(path)
        stats = compute_track_stats(segs)
        assert stats.point_count == 3
        assert stats.length_km > 0
        assert abs(stats.elevation_gain_m - 20.0) < 1e-3  # 400→420 = +20m
        assert stats.min_lat == pytest.approx(47.5)
        assert stats.max_lat == pytest.approx(47.52)
        assert stats.date == "2024-06-01"
    finally:
        path.unlink()


def test_gpx_without_namespace():
    gpx_no_ns = """<?xml version="1.0"?>
<gpx version="1.0">
  <trk><trkseg>
    <trkpt lat="51.0" lon="10.0"><ele>100</ele></trkpt>
    <trkpt lat="51.1" lon="10.1"><ele>110</ele></trkpt>
  </trkseg></trk>
</gpx>"""
    path = _write_gpx(gpx_no_ns)
    try:
        segs = read_gpx(path)
        assert len(segs) == 1
        assert len(segs[0]) == 2
    finally:
        path.unlink()
