"""Celery instance shared by the FastAPI app (enqueue + status) and the worker (execute)."""

from celery import Celery

from backend.app.settings import settings

celery_app = Celery(
    "trailprint3d",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=["backend.app.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_worker_concurrency,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_annotations={
        "backend.app.tasks.generate_preview_task": {"time_limit": settings.preview_timeout_seconds},
        "backend.app.tasks.generate_export_task": {"time_limit": settings.export_timeout_seconds},
    },
)
