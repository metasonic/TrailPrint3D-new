"""HTTP-level checks for the FastAPI app, using fastapi.testclient (no Redis needed
for these paths). Tests that touch Celery live in the curl smoke script instead."""

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import RedisError

from backend.app.main import app
from backend.app.settings import settings

client = TestClient(app)


def _redis_available() -> bool:
    try:
        return bool(Redis.from_url(str(settings.redis_url)).ping())
    except RedisError:
        return False


def test_preview_rejects_non_gpx_filename() -> None:
    r = client.post(
        "/api/v1/preview",
        files={"file": ("track.txt", b"not gpx", "application/octet-stream")},
        data={"settings": "{}"},
    )
    assert r.status_code == 415


def test_preview_rejects_invalid_settings_json() -> None:
    r = client.post(
        "/api/v1/preview",
        files={"file": ("track.gpx", b"<gpx/>", "application/gpx+xml")},
        data={"settings": '{"shape":"triangle"}'},
    )
    assert r.status_code == 422


@pytest.mark.skipif(not _redis_available(), reason="requires Redis (run scripts/dev-up.sh)")
def test_jobs_unknown_id_reports_pending() -> None:
    # Celery treats an unknown ID as PENDING by design (it can't distinguish
    # "never seen" from "queued but not picked up"). Our API surfaces that as-is.
    r = client.get("/api/v1/jobs/does-not-exist")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
