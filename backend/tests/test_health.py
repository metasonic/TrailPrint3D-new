from unittest.mock import MagicMock, patch


async def test_health_ok(client):
    with (
        patch("app.routes.health.redis_lib.from_url") as mock_redis,
        patch("app.routes.health.celery_app.control.inspect") as mock_inspect,
    ):
        mock_redis.return_value.ping.return_value = True
        mock_inspect.return_value.active.return_value = {"worker@host": []}

        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["api"] == "ok"
    assert body["redis"] == "ok"
    assert body["celery"] == "ok"


async def test_health_redis_down(client):
    with (
        patch("app.routes.health.redis_lib.from_url") as mock_redis,
        patch("app.routes.health.celery_app.control.inspect") as mock_inspect,
    ):
        mock_redis.return_value.ping.side_effect = Exception("refused")
        mock_inspect.return_value.active.return_value = None

        resp = await client.get("/api/v1/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["redis"] == "error"


async def test_health_no_workers(client):
    with (
        patch("app.routes.health.redis_lib.from_url") as mock_redis,
        patch("app.routes.health.celery_app.control.inspect") as mock_inspect,
    ):
        mock_redis.return_value.ping.return_value = True
        # inspect returns None / empty dict when no workers respond
        mock_inspect.return_value.active.return_value = None

        resp = await client.get("/api/v1/health")

    # Redis up, no workers → degraded but not 503
    assert resp.status_code == 200
    body = resp.json()
    assert body["celery"] == "degraded"
