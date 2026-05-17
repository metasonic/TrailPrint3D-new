"""Celery task for async preview generation (used when the synchronous path is too slow)."""
from __future__ import annotations

from pathlib import Path

from .celery_app import app


@app.task(bind=True, name="tasks.preview_task.generate_preview")
def generate_preview(self, file_id: str, settings_dict: dict, out_dir: str) -> dict:
    from backend.config import get_settings
    from backend.models.schemas import GenerationSettings
    from backend.pipeline.elevation import ElevationConfig
    from backend.pipeline.preview_export import generate_preview as _generate

    cfg = get_settings()
    settings = GenerationSettings(**settings_dict)
    gpx_path = cfg.OUTPUT_DIR / "uploads" / f"{file_id}.gpx"
    out_path = Path(out_dir) / f"{file_id}.glb"

    elev_cfg = ElevationConfig(
        api=settings.api,
        dataset=settings.dataset,
        opentopography_dataset=settings.opentopography_dataset,
        opentopodata_url=str(cfg.OPENTOPODATA_URL),
        opentopography_api_key=cfg.OPENTOPOGRAPHY_API_KEY,
        cache_dir=cfg.CACHE_DIR,
    )

    def _progress(pct: int):
        self.update_state(state="PROGRESS", meta={"progress": pct})

    stats = _generate(gpx_path, settings, out_path, elev_cfg, _progress)
    return {"status": "done", "glb": str(out_path), **stats}
