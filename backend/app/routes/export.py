import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models import ExportFormat, GenerationSettings, JobAccepted
from app.tasks import generate_export

router = APIRouter()

_MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("/export", response_model=JobAccepted, status_code=202)
async def create_export_job(
    gpx_file: UploadFile = File(...),
    format: ExportFormat = Form(default=ExportFormat.stl),
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

    # --- Persist GPX to job directory ---
    job_id = str(uuid.uuid4())
    job_dir = Path(settings.output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    gpx_path = job_dir / "input.gpx"
    async with aiofiles.open(gpx_path, "wb") as f:
        await f.write(content)

    # --- Enqueue ---
    generate_export.apply_async(
        args=[job_id, str(gpx_path), gen_settings.model_dump(), format.value],
        task_id=job_id,
    )

    return JobAccepted(job_id=job_id)
