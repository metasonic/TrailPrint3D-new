from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ..config import settings
from ..schemas import JobStatus, JobSubmitRequest
from ..tasks.generation import generate_model

router = APIRouter()


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _upload_path(upload_id: str) -> Path | None:
    """Return the path of an uploaded file or None if it does not exist."""
    upload_dir = Path(settings.UPLOAD_DIR)
    for ext in ("gpx", "igc", "GPX", "IGC"):
        candidate = upload_dir / f"{upload_id}.{ext}"
        if candidate.exists():
            return candidate
    # Fallback glob
    matches = list(upload_dir.glob(f"{upload_id}.*"))
    return matches[0] if matches else None


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(body: JobSubmitRequest) -> dict:
    """
    Validate the upload, create a job record, and enqueue generation.

    Returns ``{"job_id": "<uuid>"}``.
    """
    if _upload_path(body.upload_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload '{body.upload_id}' not found. Please upload a GPX/IGC file first.",
        )

    job_id = str(uuid.uuid4())
    created_at = time.time()

    initial_state = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0.0,
        "phase": "Queued",
        "message": "Waiting for a worker…",
        "files": [],
        "error": None,
        "created_at": created_at,
    }

    r = _redis()
    try:
        await r.set(f"job:{job_id}", json.dumps(initial_state))
        ttl_seconds = settings.JOB_TTL_HOURS * 3600
        await r.expire(f"job:{job_id}", ttl_seconds)
    finally:
        await r.aclose()

    # Enqueue Celery task (synchronous call — Celery's .delay() is not async).
    generate_model.delay(job_id, body.upload_id, body.params.model_dump())

    return {"job_id": job_id}


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    """Return the current status of a job."""
    r = _redis()
    try:
        raw = await r.get(f"job:{job_id}")
    finally:
        await r.aclose()

    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    data = json.loads(raw)
    return JobStatus(**data)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: str) -> None:
    """
    Request cancellation of a running job.

    Sets a Redis key that the worker polls.  The worker will terminate
    the Blender subprocess when it detects the key.
    """
    r = _redis()
    try:
        exists = await r.exists(f"job:{job_id}")
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found.",
            )
        ttl_seconds = settings.JOB_TTL_HOURS * 3600
        await r.set(f"job:{job_id}:cancel", "1", ex=ttl_seconds)
    finally:
        await r.aclose()
