"""Phase 4 integration: the pipeline now runs end-to-end against a real GPX.

Network access is required for the SRTM download on first run; subsequent runs
hit the local DEM cache. Tests gate on cache presence so CI without network
still gets coverage of the rest of the suite.
"""

from pathlib import Path

import pytest

from backend.app.models import GenerateSettings

CLUJ_GPX = Path(__file__).resolve().parent.parent / "Cluj_Eco_Trail.gpx"


def _dem_cache_present() -> bool:
    # Only run the full pipeline test when the DEM is already in the cache —
    # the network download is exercised separately by scripts/run-pipeline.sh.
    from pipeline import terrain
    from pipeline.track import compute_bbox, load_track

    if not CLUJ_GPX.exists():
        return False
    track = load_track(CLUJ_GPX)
    bbox = compute_bbox(track, padding=GenerateSettings().bbox_padding_percent)
    return terrain._cache_path(bbox).exists()


@pytest.mark.skipif(
    not _dem_cache_present(),
    reason="DEM not cached; run `scripts/run-pipeline.sh Cluj_Eco_Trail.gpx` once with network",
)
def test_pipeline_generates_glb_for_cluj(tmp_path: Path) -> None:
    from pipeline.generate import generate

    out = tmp_path / "preview.glb"
    result = generate(
        gpx_path=CLUJ_GPX,
        settings=GenerateSettings(),
        output_path=out,
        mode="preview",
        export_format="glb",
    )
    assert out.exists()
    assert out.stat().st_size > 100_000
    assert result.cache_hit is True
    assert result.format == "glb"
    assert result.mode == "preview"
    assert 40_000 < result.track_length_m < 60_000  # Cluj loop is ~51 km
    assert result.elevation_gain_m > 500


def test_generate_signature_matches_locked_contract() -> None:
    """If generate()'s signature changes, the Celery tasks break. Lock it explicitly."""
    import inspect

    from pipeline.generate import generate

    params = list(inspect.signature(generate).parameters)
    assert params == ["gpx_path", "settings", "output_path", "mode", "export_format"]
