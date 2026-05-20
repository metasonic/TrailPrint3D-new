"""Orchestrator for the GPX → 3D-printable-mesh pipeline.

This module's public contract is locked in docs/phase2_pipeline_design.md.
Phase 4 implements the body; Phase 3 only needs the signature to exist so the
FastAPI app and Celery tasks import cleanly.
"""

from pathlib import Path

from backend.app.models import ExportFormat, GenerateMode, GenerateResult, GenerateSettings


def generate(
    gpx_path: Path,
    settings: GenerateSettings,
    output_path: Path,
    mode: GenerateMode,
    export_format: ExportFormat,
) -> GenerateResult:
    """Run the full pipeline. Not yet implemented; Phase 4 fills this in."""
    raise NotImplementedError(
        "pipeline.generate.generate is implemented in Phase 4 "
        "(see docs/phase2_pipeline_design.md for the locked contract)."
    )
