import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models import GenerationSettings, JobAccepted
from app.tasks import generate_preview

router = APIRouter()

_MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/preview", response_model=JobAccepted, status_code=202)
async def create_preview_job(
    gpx_file: UploadFile = File(...),
    settings_json: str = Form(default="{}"),
):
    # --- Validate settings JSON ---
    try:
        gen_settings = GenerationSettings.model_validate_json(settings_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # --- Validate & read GPX file ---
    content = await gpx_file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = gpx_file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in (".gpx", ".igc"):
        raise HTTPException(status_code=400, detail="Only .gpx and .igc files are accepted")

    # --- Preview overrides: low resolution, no OSM elements ---
    preview_dict = gen_settings.model_dump()
    preview_dict["num_subdivisions"] = min(preview_dict["num_subdivisions"], 3)
    for flag in (
        "water_ponds", "water_small_rivers", "water_big_rivers",
        "forests", "city_boundaries", "greenspace",
        "buildings", "roads_major", "roads_medium", "roads_minor",
    ):
        preview_dict[flag] = False

    # --- Persist GPX to job directory ---
    job_id = str(uuid.uuid4())
    job_dir = Path(settings.output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    gpx_path = job_dir / "input.gpx"
    async with aiofiles.open(gpx_path, "wb") as f:
        await f.write(content)

    # --- Enqueue ---
    generate_preview.apply_async(
        args=[job_id, str(gpx_path), preview_dict],
        task_id=job_id,
    )

    return JobAccepted(job_id=job_id)
