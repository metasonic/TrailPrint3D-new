"""
Celery task that spawns a headless Blender process to produce
print-ready STL / OBJ / 3MF files using the original addon code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .celery_app import app


def _update_job(redis_url: str, job_id: str, **fields):
    """Write job state fields into Redis hash."""
    try:
        import redis as _redis

        r = _redis.from_url(redis_url)
        r.hset(f"job:{job_id}", mapping={k: str(v) for k, v in fields.items()})
        r.expire(f"job:{job_id}", 86400)  # 24 h TTL
    except Exception as exc:
        print(f"[export_task] redis update failed: {exc}", file=sys.stderr)


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
    redis_url = str(cfg.REDIS_URL) if hasattr(cfg.REDIS_URL, "__str__") else "redis://localhost:6379/0"

    job_dir = cfg.OUTPUT_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    export_dir = cfg.OUTPUT_DIR / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)

    gpx_path = cfg.OUTPUT_DIR / "uploads" / f"{file_id}.gpx"
    if not gpx_path.exists():
        # Try .igc
        gpx_path = cfg.OUTPUT_DIR / "uploads" / f"{file_id}.igc"

    config_payload = {
        "job_id": job_id,
        "gpx_path": str(gpx_path),
        "export_dir": str(export_dir),
        "export_format": export_format,
        "addon_src_dir": str(cfg.ADDON_SRC_DIR.parent),
        "settings": {
            # Map GenerationSettings fields to addon's bpy property names
            "shape": settings_dict.get("shape", "HEXAGON"),
            "objSize": settings_dict.get("obj_size_mm", 100),
            "scaleElevation": settings_dict.get("elevation_scale", 1.0),
            "num_subdivisions": settings_dict.get("num_subdivisions", 4),
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
            # Cache dirs
            "opentopoAdress": str(getattr(cfg, "OPENTOPODATA_URL", "https://api.opentopodata.org/v1/")),
        },
        "cache_dir": str(cfg.CACHE_DIR),
        "opentopography_api_key": cfg.OPENTOPOGRAPHY_API_KEY,
    }

    config_file = job_dir / "config.json"
    config_file.write_text(json.dumps(config_payload, indent=2))

    headless_script = Path(__file__).parent.parent / "blender" / "headless_generate.py"
    blender_exe = str(cfg.BLENDER_EXECUTABLE_PATH)

    cmd = [
        blender_exe,
        "--background",
        "--python", str(headless_script),
        "--",
        str(config_file),
    ]

    # Validate Blender executable exists before dispatching
    if not Path(blender_exe).exists():
        _update_job(redis_url, job_id, status="failed",
                    error=f"Blender not found at {blender_exe!r}")
        return {"status": "failed"}

    _update_job(redis_url, job_id, status="running", progress=0, message="Starting Blender...")

    BLENDER_TIMEOUT = 600  # seconds — hard cap on headless generation

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        log_file = job_dir / "blender.log"
        with open(log_file, "w") as lf:
            for line in proc.stdout:
                lf.write(line)
                lf.flush()
                # Parse progress hints from headless script stdout
                line = line.strip()
                if line.startswith("PROGRESS:"):
                    try:
                        pct = int(line.split(":")[1].strip())
                        _update_job(redis_url, job_id, progress=pct)
                    except ValueError:
                        pass
                elif line.startswith("STATUS:"):
                    msg = line[7:].strip()
                    _update_job(redis_url, job_id, message=msg)

        try:
            proc.wait(timeout=BLENDER_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            _update_job(redis_url, job_id, status="failed",
                        error=f"Blender timed out after {BLENDER_TIMEOUT}s")
            return {"status": "failed"}

        if proc.returncode != 0:
            _update_job(redis_url, job_id, status="failed", error=f"Blender exited with code {proc.returncode}")
            return {"status": "failed"}

        # Collect output files
        output_files = list(export_dir.glob("*"))
        file_names = [f.name for f in output_files]
        _update_job(redis_url, job_id, status="done", progress=100, files=json.dumps(file_names))
        return {"status": "done", "files": file_names}

    except Exception as exc:
        _update_job(redis_url, job_id, status="failed", error=str(exc))
        raise
