from celery import Celery

from app.config import settings

celery_app = Celery(
    "trailprint3d",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Track STARTED state so the job endpoint can distinguish pending from running
    task_track_started=True,
    # Ack only after the task completes so a crashed worker re-queues the job
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Store results long enough for a user session; not needed permanently
    result_expires=3600,
)
