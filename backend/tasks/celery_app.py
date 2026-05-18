from celery import Celery
from backend.config import get_settings

cfg = get_settings()
redis_url = str(cfg.REDIS_URL)

app = Celery("trailprint3d", broker=redis_url, backend=redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # Expire Celery result keys after 1 day (matches manual job: key TTL)
    result_expires=86400,
    # Hard kill at 660 s if the soft limit (620 s) is not respected
    task_soft_time_limit=620,
    task_time_limit=660,
)

# Explicitly import task modules so they are registered in both API and worker processes.
# autodiscover_tasks(["backend.tasks"]) looks for backend/tasks/tasks.py (doesn't exist)
# and silently skips; explicit imports are the reliable alternative.
from backend.tasks import export_task, preview_task  # noqa: F401, E402
