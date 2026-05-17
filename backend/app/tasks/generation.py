from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import redis

from ..celery_app import celery_app
from ..config import settings

logger = logging.getLogger(__name__)

# Path to the headless Blender script (lives alongside this package inside the
# container image at /app/blender/headless_script.py).
BLENDER_HEADLESS_SCRIPT = os.environ.get(
    "TP3D_BLENDER_SCRIPT",
    str(Path(__file__).resolve().parents[3] / "blender" / "headless_script.py"),
)


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _set_job_state(r: redis.Redis, job_id: str, state: Dict[str, Any]) -> None:
    r.set(f"job:{job_id}", json.dumps(state))
    ttl_seconds = settings.JOB_TTL_HOURS * 3600
    r.expire(f"job:{job_id}", ttl_seconds)


def _publish_progress(r: redis.Redis, job_id: str, payload: Dict[str, Any]) -> None:
    r.publish(f"job:{job_id}:progress", json.dumps(payload))


@celery_app.task(name="trailprint3d.generate_model", bind=True)
def generate_model(
    self,
    job_id: str,
    upload_id: str,
    params: Dict[str, Any],
) -> None:
    """Run a single TrailPrint3D generation job via Blender headless."""

    r = _redis_client()

    # ------------------------------------------------------------------
    # Locate the uploaded GPX / IGC file.
    # ------------------------------------------------------------------
    upload_dir = Path(settings.UPLOAD_DIR)
    gpx_path: Path | None = None
    for ext in ("gpx", "igc", "GPX", "IGC"):
        candidate = upload_dir / f"{upload_id}.{ext}"
        if candidate.exists():
            gpx_path = candidate
            break
    if gpx_path is None:
        # Try a glob as last resort.
        matches = list(upload_dir.glob(f"{upload_id}.*"))
        if matches:
            gpx_path = matches[0]

    if gpx_path is None:
        error_msg = f"Upload file not found for upload_id={upload_id}"
        logger.error(error_msg)
        state = {
            "job_id": job_id,
            "status": "failed",
            "progress": 0.0,
            "phase": "",
            "message": "",
            "files": [],
            "error": error_msg,
            "created_at": time.time(),
        }
        _set_job_state(r, job_id, state)
        _publish_progress(r, job_id, {"event": "error", "error": error_msg})
        return

    # ------------------------------------------------------------------
    # Create output directory and write params.json.
    # ------------------------------------------------------------------
    job_dir = Path(settings.OUTPUT_DIR) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    params_with_path = dict(params)
    params_with_path["gpx_file_path"] = str(gpx_path)

    params_file = job_dir / "params.json"
    params_file.write_text(json.dumps(params_with_path, indent=2))

    # ------------------------------------------------------------------
    # Store initial "running" state.
    # ------------------------------------------------------------------
    created_at = float(
        json.loads(r.get(f"job:{job_id}") or "{}").get("created_at", time.time())
    )
    state: Dict[str, Any] = {
        "job_id": job_id,
        "status": "running",
        "progress": 0.0,
        "phase": "Starting",
        "message": "Launching Blender…",
        "files": [],
        "error": None,
        "created_at": created_at,
    }
    _set_job_state(r, job_id, state)

    # ------------------------------------------------------------------
    # Build Blender subprocess command.
    # ------------------------------------------------------------------
    cmd = [
        settings.BLENDER_PATH,
        "--background",
        "--python",
        BLENDER_HEADLESS_SCRIPT,
        "--",
        "--job-id",
        job_id,
    ]

    env = os.environ.copy()
    env["TP3D_JOB_DIR"] = str(job_dir)
    env["TP3D_PARAMS_FILE"] = str(params_file)
    env["TP3D_ADDON_DIR"] = settings.BLENDER_ADDON_DIR
    env["TP3D_OPENTOPOGRAPHY_KEY"] = settings.OPENTOPOGRAPHY_KEY
    env["TP3D_DATA_DIR"] = settings.DATA_DIR
    env["TP3D_OUTPUT_DIR"] = settings.OUTPUT_DIR
    env["TP3D_JOB_ID"] = job_id
    env["TP3D_HEADLESS"] = "1"
    if settings.OPENTOPODATA_SELF_HOSTED:
        env["TP3D_OPENTOPODATA_SELF_HOSTED"] = settings.OPENTOPODATA_SELF_HOSTED

    logger.info("Launching Blender for job %s: %s", job_id, " ".join(cmd))

    # ------------------------------------------------------------------
    # Run the subprocess and stream stdout line-by-line.
    # ------------------------------------------------------------------
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        error_msg = f"Blender executable not found at {settings.BLENDER_PATH}: {exc}"
        logger.error(error_msg)
        state.update({"status": "failed", "error": error_msg})
        _set_job_state(r, job_id, state)
        _publish_progress(r, job_id, {"event": "error", "error": error_msg})
        return

    assert proc.stdout is not None  # guaranteed by stdout=PIPE

    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        if not line:
            continue

        # Check for cancellation request.
        if r.exists(f"job:{job_id}:cancel"):
            logger.info("Cancellation requested for job %s — terminating Blender.", job_id)
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            state.update(
                {
                    "status": "failed",
                    "error": "Job cancelled by user.",
                    "phase": "Cancelled",
                }
            )
            _set_job_state(r, job_id, state)
            _publish_progress(r, job_id, {"event": "error", "error": "Job cancelled by user."})
            return

        # Attempt to parse progress JSON from Blender stdout.
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Blender non-JSON line: %s", line)
                continue

            percent = data.get("percent")
            phase = data.get("phase", state.get("phase", ""))
            message = data.get("message", data.get("msg", ""))

            if percent is not None:
                # Headless overlay emits percent as 0.0–1.0 float
                progress = min(max(float(percent), 0.0), 1.0)
                state.update(
                    {
                        "progress": progress,
                        "phase": phase,
                        "message": message,
                    }
                )
                _set_job_state(r, job_id, state)

                progress_payload: Dict[str, Any] = {
                    "event": "progress",
                    "progress": progress,
                    "phase": phase,
                    "message": message,
                }
                _publish_progress(r, job_id, progress_payload)
        else:
            logger.debug("Blender stdout: %s", line)

    exit_code = proc.wait()

    # ------------------------------------------------------------------
    # Handle completion or failure.
    # ------------------------------------------------------------------
    if exit_code == 0:
        # Gather output files.
        allowed_suffixes = {".stl", ".obj", ".mtl", ".3mf", ".glb"}
        output_files = [
            f.name
            for f in job_dir.iterdir()
            if f.is_file() and f.suffix.lower() in allowed_suffixes
        ]
        output_files.sort()

        state.update(
            {
                "status": "done",
                "progress": 1.0,
                "phase": "Complete",
                "message": "Generation finished.",
                "files": output_files,
                "error": None,
            }
        )
        _set_job_state(r, job_id, state)
        _publish_progress(
            r,
            job_id,
            {
                "event": "complete",
                "progress": 1.0,
                "phase": "Complete",
                "message": "Generation finished.",
                "files": output_files,
            },
        )
        logger.info("Job %s completed successfully with files: %s", job_id, output_files)
    else:
        error_msg = f"Blender exited with code {exit_code}."
        logger.error("Job %s failed: %s", job_id, error_msg)
        state.update(
            {
                "status": "failed",
                "error": error_msg,
                "phase": "Failed",
            }
        )
        _set_job_state(r, job_id, state)
        _publish_progress(r, job_id, {"event": "error", "error": error_msg})
