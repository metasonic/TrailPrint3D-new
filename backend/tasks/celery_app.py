import os
from celery import Celery

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
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
)
