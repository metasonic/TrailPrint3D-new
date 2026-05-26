import os
import subprocess
import json
import tempfile
from rq import Worker, Queue
from redis import Redis
from loguru import logger

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(redis_url)

def run_blender_command(cmd_args):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        result_file = tmp.name

    try:
        cmd_python = ["python", "-m", "trailprint3d_backend.blender_runner"] + cmd_args + ["--result-file", result_file]
        subprocess.run(cmd_python, check=True, capture_output=True, text=True)

        with open(result_file, "r") as f:
            out_data = json.load(f)

        if out_data.get("status") == "error":
            raise Exception(f"Blender failed: {out_data.get('error')}")

        return out_data
    finally:
        if os.path.exists(result_file):
            os.remove(result_file)

def process_preview(job_id: str, gpx_path: str, output_path: str, settings: dict):
    logger.info(f"Starting preview job {job_id} for {gpx_path}")

    cmd_args = ["preview", job_id, gpx_path, output_path, "--settings", json.dumps(settings)]
    out_data = run_blender_command(cmd_args)

    logger.info(f"Preview job {job_id} complete. Output at {out_data['mesh_path']}")
    return out_data['mesh_path']

def process_export(job_id: str, gpx_path: str, output_path: str, format: str, settings: dict):
    logger.info(f"Starting export job {job_id} for {gpx_path} in {format}")

    cmd_args = ["export", job_id, gpx_path, output_path, "--format", format, "--settings", json.dumps(settings)]
    out_data = run_blender_command(cmd_args)

    logger.info(f"Export job {job_id} complete. Output at {out_data['mesh_path']}")
    return out_data['mesh_path']

if __name__ == '__main__':
    from rq import Connection
    with Connection(redis_conn):
        worker = Worker(['default'])
        worker.work()
