from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ..config import get_settings
from ..models.schemas import ExportRequest, ExportResponse, JobStatus

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export", response_model=ExportResponse)
async def start_export(body: ExportRequest):
    cfg = get_settings()

    # Check file exists
    gpx_path: Path | None = None
    for ext in (".gpx", ".igc"):
        p = cfg.OUTPUT_DIR / "uploads" / f"{body.file_id}{ext}"
        if p.exists():
            gpx_path = p
            break
    if gpx_path is None:
        raise HTTPException(status_code=404, detail=f"File {body.file_id!r} not found")

    job_id = str(uuid.uuid4())

    # Initialize job status in Redis
    try:
        import redis as _redis

        r = _redis.from_url(str(cfg.REDIS_URL))
        r.hset(
            f"job:{job_id}",
            mapping={"status": "pending", "progress": "0", "message": "Queued", "files": "[]"},
        )
        r.expire(f"job:{job_id}", 86400)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}")

    # Dispatch Celery task
    from ..tasks.export_task import export_model

    export_model.apply_async(
        args=[job_id, body.file_id, body.settings.model_dump(), body.format],
        task_id=job_id,
    )

    return ExportResponse(job_id=job_id)


@router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    cfg = get_settings()
    try:
        import redis as _redis

        r = _redis.from_url(str(cfg.REDIS_URL))
        data = r.hgetall(f"job:{job_id}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}")

    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    def _s(v) -> str:
        return v.decode() if isinstance(v, bytes) else str(v)

    files: list[str] = []
    raw_files = data.get(b"files", data.get("files", "[]"))
    try:
        files = json.loads(_s(raw_files))
    except Exception:
        pass

    return JobStatus(
        job_id=job_id,
        status=_s(data.get(b"status", data.get("status", "pending"))),
        progress=int(_s(data.get(b"progress", data.get("progress", 0)))),
        message=_s(data.get(b"message", data.get("message", ""))),
        error=_s(data.get(b"error", data.get("error", ""))) or None,
        files=files,
    )


@router.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    cfg = get_settings()

    # Sanitize
    if not all(c.isalnum() or c in "-_." for c in filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = cfg.OUTPUT_DIR / "exports" / job_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = path.suffix.lower()
    media_types = {
        ".stl": "model/stl",
        ".obj": "model/obj",
        ".3mf": "model/3mf",
        ".glb": "model/gltf-binary",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type, filename=filename)
