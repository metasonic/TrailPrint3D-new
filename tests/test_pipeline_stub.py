"""Phase 3 only verifies the pipeline contract exists. Phase 4 will replace these."""

from pathlib import Path

import pytest

from backend.app.models import GenerateSettings
from pipeline.generate import generate


def test_generate_is_callable_and_unimplemented(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):
        generate(
            gpx_path=tmp_path / "anything.gpx",
            settings=GenerateSettings(),
            output_path=tmp_path / "out.glb",
            mode="preview",
            export_format="glb",
        )
