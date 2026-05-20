import redis as redis_lib
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.celery_app import celery_app
from app.config import settings
from app.models import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
def health_check():
    # --- Redis ---
    redis_status: str
    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"

    # --- Celery workers ---
    celery_status: str
    try:
        inspector = celery_app.control.inspect(timeout=1)
        active = inspector.active()
        if active:
            celery_status = "ok"
        elif redis_status == "ok":
            # Broker reachable but no workers responded
            celery_status = "degraded"
        else:
            celery_status = "error"
    except Exception:
        celery_status = "error"

    overall = (
        "ok"
        if redis_status == "ok" and celery_status in ("ok", "degraded")
        else "error"
    )

    body = HealthStatus(
        status=overall,
        api="ok",
        redis=redis_status,
        celery=celery_status,
    )
    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content=body.model_dump(), status_code=status_code)
