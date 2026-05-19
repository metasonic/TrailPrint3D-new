from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

import redis.asyncio as _redis
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings
from ..models.schemas import ExportRequest, ExportResponse, JobStatus

router = APIRouter(prefix="/api", tags=["export"])
logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# Case-insensitive so Blender's uppercase .STL/.OBJ outputs are accepted
_SAFE_FILENAME_RE = re.compile(r"^[0-9a-zA-Z_\-]+\.(stl|obj|3mf|glb)$", re.IGNORECASE)
_VALID_STATUSES = {"pending", "running", "done", "failed"}

# Module-level connection pool — shared across all requests in this process
_pool: _redis.ConnectionPool | None = None


def _get_redis() -> _redis.Redis:
    global _pool
    if _pool is None:
        _pool = _redis.ConnectionPool.from_url(str(get_settings().REDIS_URL))
    return _redis.Redis(connection_pool=_pool)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def _validate_uuid(value: str, field: str) -> None:
    if not _UUID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


@router.post("/export", response_model=ExportResponse)
async def start_export(body: ExportRequest):
    _validate_uuid(body.file_id, "file_id")
    cfg = get_settings()

    gpx_path: Path | None = None
    for ext in (".gpx", ".igc"):
        p = cfg.OUTPUT_DIR / "uploads" / f"{body.file_id}{ext}"
        if p.exists():
            gpx_path = p
            break
    if gpx_path is None:
        raise HTTPException(status_code=404, detail="File not found")

    job_id = str(uuid.uuid4())

    try:
        r = _get_redis()
        await r.hset(
            f"job:{job_id}",
            mapping={"status": "pending", "progress": "0", "message": "Queued", "files": "[]"},
        )
        await r.expire(f"job:{job_id}", 86400)
    except Exception:
        logger.exception("Redis unavailable when creating job %s", job_id)
        raise HTTPException(status_code=503, detail="Queue temporarily unavailable")

    from ..tasks.export_task import export_model

    try:
        export_model.apply_async(
            args=[job_id, body.file_id, body.settings.model_dump(), body.format],
            task_id=job_id,
        )
    except Exception:
        logger.exception("Failed to enqueue export task for job %s", job_id)
        try:
            await _get_redis().delete(f"job:{job_id}")
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Queue temporarily unavailable")

    return ExportResponse(job_id=job_id)


@router.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    _validate_uuid(job_id, "job_id")
    try:
        r = _get_redis()
        data = await r.hgetall(f"job:{job_id}")
    except Exception:
        logger.exception("Redis unavailable when fetching job %s", job_id)
        raise HTTPException(status_code=503, detail="Queue temporarily unavailable")

    if not data:
        raise HTTPException(status_code=404, detail="Job not found")

    def _s(v) -> str:
        return v.decode() if isinstance(v, bytes) else str(v)

    files: list[str] = []
    raw_files = data.get(b"files", data.get("files", "[]"))
    try:
        files = json.loads(_s(raw_files))
    except Exception:
        pass

    # Guard against corrupted/unexpected status values from Redis
    raw_status = _s(data.get(b"status", data.get("status", "pending")))
    status = raw_status if raw_status in _VALID_STATUSES else "failed"

    return JobStatus(
        job_id=job_id,
        status=status,
        progress=int(_s(data.get(b"progress", data.get("progress", 0)))),
        message=_s(data.get(b"message", data.get("message", ""))),
        error=_s(data.get(b"error", data.get("error", ""))) or None,
        files=files,
    )


@router.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    _validate_uuid(job_id, "job_id")
    cfg = get_settings()

    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    exports_dir = (cfg.OUTPUT_DIR / "exports").resolve()
    path = (cfg.OUTPUT_DIR / "exports" / job_id / filename).resolve()

    # Path-traversal jail: resolved path must stay inside exports dir
    if not path.is_relative_to(exports_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
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
