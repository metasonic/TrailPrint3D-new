"""FastAPI app: upload GPX, enqueue Celery job, poll status, serve outputs."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated, Literal

from celery.result import AsyncResult
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import RedisError

from backend.app.celery_app import celery_app
from backend.app.models import (
    ExportFormat,
    GenerateSettings,
    HealthResponse,
    JobEnqueueResponse,
    JobInfo,
    JobStatus,
)
from backend.app.settings import settings
from backend.app.tasks import generate_export_task, generate_preview_task

app = FastAPI(title="TrailPrint3D Web", version="0.1.0")

app.mount("/files", StaticFiles(directory=str(settings.output_dir)), name="files")

_redis = Redis.from_url(str(settings.redis_url), decode_responses=True)


def _parse_settings(settings_json: str) -> GenerateSettings:
    try:
        return GenerateSettings.model_validate_json(settings_json)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc


def _save_upload(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith(".gpx"):
        raise HTTPException(status_code=415, detail="Only .gpx files are accepted")
    body = file.file.read()
    if len(body) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="GPX exceeds MAX_UPLOAD_SIZE_MB")
    upload_id = uuid.uuid4().hex
    upload_path = settings.output_dir / "uploads" / f"{upload_id}.gpx"
    upload_path.write_bytes(body)
    return upload_path


_CELERY_TO_JOB_STATUS = {
    "PENDING": JobStatus.pending,
    "RECEIVED": JobStatus.pending,
    "STARTED": JobStatus.processing,
    "RETRY": JobStatus.processing,
    "SUCCESS": JobStatus.completed,
    "FAILURE": JobStatus.failed,
    "REVOKED": JobStatus.failed,
}


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    redis_ok = False
    celery_ok = False
    try:
        redis_ok = bool(_redis.ping())
    except RedisError:
        redis_ok = False
    if redis_ok:
        try:
            celery_ok = bool(celery_app.control.ping(timeout=1.0))
        except Exception:
            celery_ok = False
    overall: Literal["ok", "degraded"] = "ok" if (redis_ok and celery_ok) else "degraded"
    return HealthResponse(status=overall, redis=redis_ok, celery=celery_ok)


@app.post("/api/v1/preview", response_model=JobEnqueueResponse)
def enqueue_preview(
    file: Annotated[UploadFile, File()],
    settings_json: Annotated[str, Form(alias="settings")],
) -> JobEnqueueResponse:
    cfg = _parse_settings(settings_json)
    upload_path = _save_upload(file)
    async_result = generate_preview_task.delay(str(upload_path), cfg.model_dump_json())
    return JobEnqueueResponse(job_id=async_result.id, status=JobStatus.pending)


@app.post("/api/v1/export", response_model=JobEnqueueResponse)
def enqueue_export(
    file: Annotated[UploadFile, File()],
    settings_json: Annotated[str, Form(alias="settings")],
    fmt: Annotated[ExportFormat, Form(alias="format")],
) -> JobEnqueueResponse:
    cfg = _parse_settings(settings_json)
    upload_path = _save_upload(file)
    async_result = generate_export_task.delay(str(upload_path), cfg.model_dump_json(), fmt)
    return JobEnqueueResponse(job_id=async_result.id, status=JobStatus.pending)


@app.get("/api/v1/jobs/{job_id}", response_model=JobInfo)
def job_status(job_id: str) -> JobInfo:
    result = AsyncResult(job_id, app=celery_app)
    status = _CELERY_TO_JOB_STATUS.get(result.status, JobStatus.pending)
    if status is JobStatus.completed:
        payload = result.result or {}
        filename = payload.get("output_filename") if isinstance(payload, dict) else None
        return JobInfo(
            job_id=job_id,
            status=status,
            result_url=f"/files/{filename}" if filename else None,
        )
    if status is JobStatus.failed:
        return JobInfo(job_id=job_id, status=status, error=str(result.result))
    return JobInfo(job_id=job_id, status=status)


@app.exception_handler(ValidationError)
def _validation_handler(_: object, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": json.loads(exc.json())})
