import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# POST /preview
# ---------------------------------------------------------------------------

async def test_preview_returns_job_id(client, gpx_bytes, tmp_path):
    with (
        patch("app.routes.preview.settings") as mock_cfg,
        patch("app.routes.preview.generate_preview") as mock_task,
    ):
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)
        mock_task.apply_async.return_value = MagicMock()

        resp = await client.post(
            "/api/v1/preview",
            files={"gpx_file": ("track.gpx", gpx_bytes, "application/gpx+xml")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    # job_id must be a valid UUID
    uuid.UUID(body["job_id"])


async def test_preview_rejects_non_gpx(client, tmp_path):
    with patch("app.routes.preview.settings") as mock_cfg:
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)

        resp = await client.post(
            "/api/v1/preview",
            files={"gpx_file": ("model.stl", b"binary data", "application/octet-stream")},
        )

    assert resp.status_code == 400


async def test_preview_rejects_oversized_file(client, tmp_path):
    big = b"x" * (11 * 1024 * 1024)  # 11 MB
    with patch("app.routes.preview.settings") as mock_cfg:
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)

        resp = await client.post(
            "/api/v1/preview",
            files={"gpx_file": ("big.gpx", big, "application/gpx+xml")},
        )

    assert resp.status_code == 413


async def test_preview_rejects_invalid_settings_json(client, gpx_bytes, tmp_path):
    with patch("app.routes.preview.settings") as mock_cfg:
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)

        resp = await client.post(
            "/api/v1/preview",
            files={"gpx_file": ("track.gpx", gpx_bytes, "application/gpx+xml")},
            data={"settings_json": '{"obj_size": -999}'},  # violates ge=5
        )

    assert resp.status_code == 422


async def test_preview_overrides_osm_flags(client, gpx_bytes, tmp_path):
    """Settings with OSM elements enabled must be silently overridden to False."""
    with (
        patch("app.routes.preview.settings") as mock_cfg,
        patch("app.routes.preview.generate_preview") as mock_task,
    ):
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)
        captured = {}

        def capture_apply_async(args, task_id):
            captured["settings_dict"] = args[2]
            return MagicMock()

        mock_task.apply_async.side_effect = capture_apply_async

        settings_with_osm = json.dumps({"forests": True, "buildings": True})
        await client.post(
            "/api/v1/preview",
            files={"gpx_file": ("track.gpx", gpx_bytes, "application/gpx+xml")},
            data={"settings_json": settings_with_osm},
        )

    assert captured["settings_dict"]["forests"] is False
    assert captured["settings_dict"]["buildings"] is False


# ---------------------------------------------------------------------------
# POST /export
# ---------------------------------------------------------------------------

async def test_export_returns_job_id(client, gpx_bytes, tmp_path):
    with (
        patch("app.routes.export.settings") as mock_cfg,
        patch("app.routes.export.generate_export") as mock_task,
    ):
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)
        mock_task.apply_async.return_value = MagicMock()

        resp = await client.post(
            "/api/v1/export",
            files={"gpx_file": ("track.gpx", gpx_bytes, "application/gpx+xml")},
            data={"format": "stl"},
        )

    assert resp.status_code == 202
    uuid.UUID(resp.json()["job_id"])


async def test_export_rejects_invalid_format(client, gpx_bytes, tmp_path):
    with patch("app.routes.export.settings") as mock_cfg:
        mock_cfg.max_upload_size_mb = 10
        mock_cfg.output_dir = str(tmp_path)

        resp = await client.post(
            "/api/v1/export",
            files={"gpx_file": ("track.gpx", gpx_bytes, "application/gpx+xml")},
            data={"format": "png"},  # not a valid export format
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

async def test_job_not_found(client, tmp_path):
    with (
        patch("app.routes.jobs.AsyncResult") as mock_ar,
        patch("app.routes.jobs.settings") as mock_cfg,
    ):
        mock_cfg.output_dir = str(tmp_path)
        mock_ar.return_value.state = "PENDING"

        resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_job_pending(client, tmp_path):
    job_id = str(uuid.uuid4())
    # Create job dir so the endpoint knows it exists
    (Path(tmp_path) / job_id).mkdir()

    with (
        patch("app.routes.jobs.AsyncResult") as mock_ar,
        patch("app.routes.jobs.settings") as mock_cfg,
    ):
        mock_cfg.output_dir = str(tmp_path)
        mock_ar.return_value.state = "PENDING"

        resp = await client.get(f"/api/v1/jobs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["progress"] == 0


async def test_job_processing(client, tmp_path):
    job_id = str(uuid.uuid4())

    with (
        patch("app.routes.jobs.AsyncResult") as mock_ar,
        patch("app.routes.jobs.settings") as mock_cfg,
    ):
        mock_cfg.output_dir = str(tmp_path)
        ar = MagicMock()
        ar.state = "PROGRESS"
        ar.info = {"progress": 45, "phase": "Fetching elevation"}
        mock_ar.return_value = ar

        resp = await client.get(f"/api/v1/jobs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processing"
    assert body["progress"] == 45


async def test_job_completed(client, tmp_path):
    job_id = str(uuid.uuid4())
    result_url = f"/files/{job_id}/output.glb"

    with (
        patch("app.routes.jobs.AsyncResult") as mock_ar,
        patch("app.routes.jobs.settings") as mock_cfg,
    ):
        mock_cfg.output_dir = str(tmp_path)
        ar = MagicMock()
        ar.state = "SUCCESS"
        ar.result = result_url
        mock_ar.return_value = ar

        resp = await client.get(f"/api/v1/jobs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["result_url"] == result_url


async def test_job_failed(client, tmp_path):
    job_id = str(uuid.uuid4())

    with (
        patch("app.routes.jobs.AsyncResult") as mock_ar,
        patch("app.routes.jobs.settings") as mock_cfg,
    ):
        mock_cfg.output_dir = str(tmp_path)
        ar = MagicMock()
        ar.state = "FAILURE"
        ar.result = RuntimeError("Blender exited with code 1")
        mock_ar.return_value = ar

        resp = await client.get(f"/api/v1/jobs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] is not None
