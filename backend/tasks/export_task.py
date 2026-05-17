"""
Celery task that spawns a headless Blender process to produce
print-ready STL / OBJ / 3MF files using the original addon code.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

import redis as _redis

from .celery_app import app

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SAFE_FILENAME_RE = re.compile(r"^[0-9a-zA-Z_\-]+\.(stl|obj|3mf|glb)$", re.IGNORECASE)
BLENDER_TIMEOUT = 600  # hard cap on headless generation (seconds)


def _update_job(r: _redis.Redis, job_id: str, **fields) -> None:
    """Write job state fields into the Redis hash for this job."""
    try:
        r.hset(f"job:{job_id}", mapping={k: str(v) for k, v in fields.items()})
        r.expire(f"job:{job_id}", 86400)
    except Exception:
        logger.exception("Redis update failed for job %s", job_id)


@app.task(bind=True, name="tasks.export_task.export_model")
def export_model(
    self,
    job_id: str,
    file_id: str,
    settings_dict: dict,
    export_format: str,
) -> dict:
    from backend.config import get_settings

    cfg = get_settings()
    # Single Redis connection for the lifetime of this task
    r = _redis.from_url(str(cfg.REDIS_URL))

    # Defence-in-depth: re-validate IDs even though the router already checked them.
    # A compromised Redis broker could enqueue tasks with malicious path components.
    if not _UUID_RE.match(job_id) or not _UUID_RE.match(file_id):
        logger.error("Invalid job_id or file_id received by Celery task: job=%s file=%s", job_id, file_id)
        return {"status": "failed", "error": "Invalid task arguments"}

    # Mark running immediately so any mkdir failure is captured in Redis
    _update_job(r, job_id, status="running", progress=0, message="Preparing...")

    try:
        job_dir = cfg.OUTPUT_DIR / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        export_dir = cfg.OUTPUT_DIR / "exports" / job_id
        export_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Failed to create directories for job %s", job_id)
        _update_job(r, job_id, status="failed", error="Failed to create job directories")
        return {"status": "failed"}

    # Verify the source GPX/IGC file exists before starting Blender
    gpx_path = cfg.OUTPUT_DIR / "uploads" / f"{file_id}.gpx"
    if not gpx_path.exists():
        gpx_path = cfg.OUTPUT_DIR / "uploads" / f"{file_id}.igc"
    if not gpx_path.exists():
        _update_job(r, job_id, status="failed", error="Source GPX/IGC file not found")
        logger.error("GPX/IGC file not found for file_id=%s job=%s", file_id, job_id)
        return {"status": "failed"}

    # Cap subdivisions to avoid runaway memory/CPU usage on export
    num_subdivisions = min(settings_dict.get("num_subdivisions", 4), 6)

    config_payload = {
        "job_id": job_id,
        "gpx_path": str(gpx_path),
        "export_dir": str(export_dir),
        "export_format": export_format,
        "addon_src_dir": str(cfg.ADDON_SRC_DIR.parent),
        "settings": {
            "shape": settings_dict.get("shape", "HEXAGON"),
            "objSize": settings_dict.get("obj_size_mm", 100),
            "rectangleHeight": settings_dict.get("rectangle_height", 100),
            "ellipseRatio": settings_dict.get("ellipse_ratio", 0.75),
            "scaleElevation": settings_dict.get("elevation_scale", 1.0),
            "num_subdivisions": num_subdivisions,
            "pathThickness": settings_dict.get("path_thickness", 1.2),
            "pathScale": settings_dict.get("path_scale", 0.8),
            "shapeRotation": settings_dict.get("shape_rotation", 0),
            "overwritePathElevation": settings_dict.get("overwrite_path_elevation", True),
            "minThickness": settings_dict.get("min_thickness", 2.0),
            "fixedElevationScale": settings_dict.get("fixed_elevation_scale", False),
            "plateThickness": settings_dict.get("plate_thickness", 5.0),
            "singleColorMode": settings_dict.get("single_color_mode", False),
            "api": settings_dict.get("api", "TERRAIN-TILES"),
            "dataset": settings_dict.get("dataset", "aster30m"),
            "openTopographyDataset": settings_dict.get("opentopography_dataset", "SRTMGL1"),
            "scalemode": settings_dict.get("scale_mode", "FACTOR"),
            "elementMode": settings_dict.get("element_mode", "PAINT"),
            "trailName": settings_dict.get("trail_name", ""),
            "xTerrainOffset": settings_dict.get("x_terrain_offset", 0.0),
            "yTerrainOffset": settings_dict.get("y_terrain_offset", 0.0),
            "col_wPondsActive": settings_dict.get("water_ponds", False),
            "col_wSmallRiversActive": settings_dict.get("water_small_rivers", False),
            "col_wBigRiversActive": settings_dict.get("water_big_rivers", False),
            "col_fActive": settings_dict.get("include_forests", False),
            "col_cActive": settings_dict.get("include_city", False),
            "col_grActive": settings_dict.get("include_greenspace", False),
            "col_faActive": settings_dict.get("include_farmland", False),
            "col_glActive": settings_dict.get("include_glacier", False),
            "el_bActive": settings_dict.get("include_buildings", False),
            "el_sBigActive": settings_dict.get("roads_big", False),
            "el_sMedActive": settings_dict.get("roads_med", False),
            "el_sSmallActive": settings_dict.get("roads_small", False),
            "el_oActive": settings_dict.get("include_ocean", False),
            "disableCache": False,
            "apiRetries": 5,
            "opentopoAdress": str(getattr(cfg, "OPENTOPODATA_URL", "https://api.opentopodata.org/v1/")),
        },
        "cache_dir": str(cfg.CACHE_DIR),
        # API key is NOT stored in this file — it is passed as an environment variable
    }

    config_file = job_dir / "config.json"
    config_file.write_text(json.dumps(config_payload, indent=2))

    headless_script = Path(__file__).parent.parent / "blender" / "headless_generate.py"
    blender_exe = str(cfg.BLENDER_EXECUTABLE_PATH)

    if not Path(blender_exe).exists():
        _update_job(r, job_id, status="failed", error="Blender not found at configured path")
        logger.error("Blender not found at %s", blender_exe)
        return {"status": "failed"}

    cmd = [
        blender_exe,
        "--background",
        "--python", str(headless_script),
        "--",
        str(config_file),
    ]

    # Pass API key via environment variable, not config file on disk
    proc_env = dict(os.environ)
    proc_env["OPENTOPOGRAPHY_API_KEY"] = cfg.OPENTOPOGRAPHY_API_KEY

    _update_job(r, job_id, status="running", progress=0, message="Starting Blender...")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=proc_env,
        )

        # Drain stdout in a thread while enforcing a hard timeout.
        # The naive "for line in proc.stdout + proc.wait(timeout=N)" pattern
        # does NOT enforce the timeout: the for-loop blocks until EOF regardless.
        output_lines: list[str] = []

        def _drain():
            assert proc.stdout is not None
            for line in proc.stdout:
                output_lines.append(line)

        drain_thread = threading.Thread(target=_drain, daemon=True)
        drain_thread.start()
        drain_thread.join(timeout=BLENDER_TIMEOUT)

        if drain_thread.is_alive():
            proc.kill()
            drain_thread.join(timeout=5)
            _update_job(r, job_id, status="failed",
                        error=f"Generation timed out after {BLENDER_TIMEOUT}s")
            return {"status": "failed"}

        proc.wait()

        # Write log and parse progress/status messages for Redis
        log_file = job_dir / "blender.log"
        with open(log_file, "w") as lf:
            for line in output_lines:
                lf.write(line)
                stripped = line.strip()
                if stripped.startswith("PROGRESS:"):
                    try:
                        pct = int(stripped.split(":")[1].strip())
                        _update_job(r, job_id, progress=pct)
                    except ValueError:
                        pass
                elif stripped.startswith("STATUS:"):
                    # Sanitise message: printable ASCII only, max 200 chars
                    msg = stripped[7:].strip()
                    msg = "".join(c for c in msg if c.isprintable() and ord(c) < 128)[:200]
                    _update_job(r, job_id, message=msg)

        if proc.returncode != 0:
            # Log the actual exit code server-side; return a generic message to Redis
            logger.error("Blender exited with code %d for job %s", proc.returncode, job_id)
            _update_job(r, job_id, status="failed", error="Generation failed")
            return {"status": "failed"}

        # Collect and validate output files before marking done
        output_files = [
            f for f in export_dir.glob("*")
            if _SAFE_FILENAME_RE.match(f.name)
        ]
        if not output_files:
            _update_job(r, job_id, status="failed", error="No output files produced")
            return {"status": "failed"}

        file_names = [f.name for f in output_files]
        _update_job(r, job_id, status="done", progress=100, files=json.dumps(file_names))
        return {"status": "done", "files": file_names}

    except Exception:
        logger.exception("Export task failed for job %s", job_id)
        _update_job(r, job_id, status="failed", error="Internal export error")
        raise

    finally:
        # Remove config.json — it contains internal paths; log file is kept for debugging
        try:
            config_file.unlink(missing_ok=True)
        except OSError:
            pass
