"""Schema-level checks for GenerateSettings (the locked Phase 2 contract)."""

import pytest
from pydantic import ValidationError

from backend.app.models import GenerateSettings


def test_defaults_match_phase2_design() -> None:
    s = GenerateSettings()
    assert s.shape == "hexagon"
    assert s.terrain_scale == 1.0
    assert s.track_thickness_mm == 1.2
    assert s.frame_thickness_mm == 5.0
    assert s.bbox_padding_percent == 0.1
    assert s.model_size_mm == 100.0
    assert s.min_base_thickness_mm == 2.0
    assert s.preview_subdivisions == 2
    assert s.export_subdivisions == 4


def test_shape_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        GenerateSettings(shape="triangle")  # type: ignore[arg-type]


def test_bbox_padding_bounds() -> None:
    with pytest.raises(ValidationError):
        GenerateSettings(bbox_padding_percent=-0.01)
    with pytest.raises(ValidationError):
        GenerateSettings(bbox_padding_percent=1.01)
    GenerateSettings(bbox_padding_percent=0.0)
    GenerateSettings(bbox_padding_percent=1.0)


def test_track_thickness_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        GenerateSettings(track_thickness_mm=0.0)
