import json
import subprocess
from pathlib import Path

from app.celery_app import celery_app
from app.config import settings


def _run_blender(
    self,
    job_id: str,
    gpx_path: str,
    settings_dict: dict,
    mode: str,
    fmt: str,
    timeout: int,
) -> str:
    """
    Shared implementation for preview and export tasks.

    Writes settings JSON, invokes Blender headlessly, parses progress lines
    from stdout, updates Celery state, and returns the result URL.
    """
    job_dir = Path(settings.output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    settings_path = job_dir / "settings.json"
    settings_path.write_text(json.dumps(settings_dict))

    ext = "glb" if mode == "preview" else fmt
    output_path = str(job_dir / f"output.{ext}")

    cmd = [
        settings.blender_executable,
        "--background",
        "--python", settings.blender_script_path,
        "--",
        "--gpx", gpx_path,
        "--settings", str(settings_path),
        "--output", output_path,
        "--mode", mode,
        "--format", ext,
    ]

    self.update_state(state="PROGRESS", meta={"progress": 5, "phase": "Starting Blender"})

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"Blender executable not found at {settings.blender_executable}"
        )

    for line in process.stdout:
        line = line.strip()
        # The Blender script emits JSON progress lines: {"progress": N, "phase": "..."}
        if line.startswith('{"progress"'):
            try:
                data = json.loads(line)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "progress": int(data.get("progress", 0)),
                        "phase": data.get("phase", ""),
                    },
                )
            except (json.JSONDecodeError, ValueError):
                pass

    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Blender exited with code {process.returncode}")

    if not Path(output_path).exists():
        raise RuntimeError("Blender did not produce an output file")

    return f"/files/{job_id}/output.{ext}"


@celery_app.task(
    bind=True,
    name="app.tasks.generate_preview",
    soft_time_limit=settings.preview_timeout_seconds,
    time_limit=settings.preview_timeout_seconds + 30,
)
def generate_preview(self, job_id: str, gpx_path: str, settings_dict: dict) -> str:
    return _run_blender(
        self,
        job_id=job_id,
        gpx_path=gpx_path,
        settings_dict=settings_dict,
        mode="preview",
        fmt="glb",
        timeout=settings.preview_timeout_seconds,
    )


@celery_app.task(
    bind=True,
    name="app.tasks.generate_export",
    soft_time_limit=settings.export_timeout_seconds,
    time_limit=settings.export_timeout_seconds + 30,
)
def generate_export(
    self, job_id: str, gpx_path: str, settings_dict: dict, fmt: str
) -> str:
    return _run_blender(
        self,
        job_id=job_id,
        gpx_path=gpx_path,
        settings_dict=settings_dict,
        mode="export",
        fmt=fmt,
        timeout=settings.export_timeout_seconds,
    )
