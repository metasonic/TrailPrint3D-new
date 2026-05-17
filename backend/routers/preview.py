from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings
from ..models.schemas import PreviewRequest, PreviewResponse
from ..pipeline.elevation import ElevationConfig

router = APIRouter(prefix="/api", tags=["preview"])
logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Cap concurrent preview generations to avoid exhausting the thread pool
_preview_semaphore = asyncio.Semaphore(4)

PREVIEW_TIMEOUT_S = 120.0


def _validate_uuid(value: str, field: str) -> None:
    if not _UUID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


@router.post("/preview", response_model=PreviewResponse)
async def generate_preview(body: PreviewRequest):
    _validate_uuid(body.file_id, "file_id")
    cfg = get_settings()
    settings = body.settings

    gpx_path: Path | None = None
    for ext in (".gpx", ".igc"):
        p = cfg.OUTPUT_DIR / "uploads" / f"{body.file_id}{ext}"
        if p.exists():
            gpx_path = p
            break

    if gpx_path is None:
        raise HTTPException(status_code=404, detail="File not found")

    out_path = cfg.OUTPUT_DIR / "preview" / f"{body.file_id}.glb"

    elev_cfg = ElevationConfig(
        api=settings.api,
        dataset=settings.dataset,
        opentopography_dataset=settings.opentopography_dataset,
        opentopodata_url=cfg.OPENTOPODATA_URL,
        opentopography_api_key=cfg.OPENTOPOGRAPHY_API_KEY,
        cache_dir=cfg.CACHE_DIR,
        num_subdivisions=min(settings.num_subdivisions, 4),
    )

    try:
        from ..pipeline.preview_export import generate_preview as _gen

        async with _preview_semaphore:
            terrain_stats = await asyncio.wait_for(
                asyncio.to_thread(_gen, gpx_path, settings, out_path, elev_cfg),
                timeout=PREVIEW_TIMEOUT_S,
            )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Preview generation timed out")
    except Exception as exc:
        logger.exception("Preview generation failed for file_id=%s", body.file_id)
        raise HTTPException(status_code=500, detail="Preview generation failed")

    glb_url = f"/api/preview/{body.file_id}.glb"
    return PreviewResponse(glb_url=glb_url, terrain_stats=terrain_stats)


@router.get("/preview/{filename}")
async def serve_preview(filename: str):
    cfg = get_settings()
    name = filename[:-4] if filename.endswith(".glb") else ""
    if not name or not _UUID_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    preview_dir = (cfg.OUTPUT_DIR / "preview").resolve()
    path = (cfg.OUTPUT_DIR / "preview" / filename).resolve()
    if not path.is_relative_to(preview_dir) or not path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(str(path), media_type="model/gltf-binary", filename=filename)
