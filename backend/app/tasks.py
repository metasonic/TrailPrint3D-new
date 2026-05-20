"""Celery tasks. Each task is a thin wrapper around `pipeline.generate.generate()`."""

from pathlib import Path
from typing import Any

from celery import Task

from backend.app.celery_app import celery_app
from backend.app.models import ExportFormat, GenerateSettings
from backend.app.settings import settings
from pipeline.generate import generate


@celery_app.task(bind=True, name="backend.app.tasks.generate_preview_task")  # type: ignore[untyped-decorator]
def generate_preview_task(self: Task, gpx_path: str, settings_json: str) -> dict[str, Any]:
    cfg = GenerateSettings.model_validate_json(settings_json)
    output_path = settings.output_dir / f"{self.request.id}.glb"
    result = generate(
        gpx_path=Path(gpx_path),
        settings=cfg,
        output_path=output_path,
        mode="preview",
        export_format="glb",
    )
    return result.model_dump(mode="json")


@celery_app.task(bind=True, name="backend.app.tasks.generate_export_task")  # type: ignore[untyped-decorator]
def generate_export_task(
    self: Task, gpx_path: str, settings_json: str, fmt: ExportFormat
) -> dict[str, Any]:
    cfg = GenerateSettings.model_validate_json(settings_json)
    output_path = settings.output_dir / f"{self.request.id}.{fmt}"
    result = generate(
        gpx_path=Path(gpx_path),
        settings=cfg,
        output_path=output_path,
        mode="export",
        export_format=fmt,
    )
    return result.model_dump(mode="json")
