from celery import Celery

from .config import settings

celery_app = Celery(
    "trailprint3d",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=1800,
    worker_max_tasks_per_child=10,
)
