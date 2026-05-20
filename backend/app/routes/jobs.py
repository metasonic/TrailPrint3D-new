from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException

from app.celery_app import celery_app
from app.config import settings
from app.models import JobState, JobStatus

router = APIRouter()

# Map Celery built-in states to our JobState enum
_STATE_MAP: dict[str, JobState] = {
    "PENDING": JobState.pending,
    "RECEIVED": JobState.pending,
    "STARTED": JobState.processing,
    "RETRY": JobState.processing,
    "PROGRESS": JobState.processing,
    "SUCCESS": JobState.completed,
    "FAILURE": JobState.failed,
    "REVOKED": JobState.failed,
}


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        # Celery returns PENDING both for "queued but not started" and for
        # completely unknown IDs.  We distinguish by checking whether a job
        # directory was created by the route handler at enqueue time.
        job_dir = Path(settings.output_dir) / job_id
        if not job_dir.exists():
            raise HTTPException(status_code=404, detail="Job not found")

    status = _STATE_MAP.get(state, JobState.processing)

    progress = 0
    result_url = None
    error = None

    if state == "PROGRESS":
        meta = result.info or {}
        progress = int(meta.get("progress", 0))
    elif state == "STARTED":
        progress = 5
    elif state == "SUCCESS":
        progress = 100
        result_url = result.result
    elif state in ("FAILURE", "REVOKED"):
        progress = 100
        error = str(result.result) if result.result else "Job failed"

    return JobStatus(
        job_id=job_id,
        status=status,
        progress=progress,
        result_url=result_url,
        error=error,
    )
