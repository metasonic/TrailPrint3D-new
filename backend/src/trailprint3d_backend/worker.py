import os
import subprocess
import json
from rq import Worker, Queue
from redis import Redis
from loguru import logger

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(redis_url)

def process_preview(job_id: str, gpx_path: str, output_path: str, settings: dict):
    logger.info(f"Starting preview job {job_id} for {gpx_path}")
    cmd_python = [
        "python", "-m", "trailprint3d_backend.blender_runner",
        "preview", job_id, gpx_path, output_path, json.dumps(settings)
    ]
    result = subprocess.run(cmd_python, check=True, capture_output=True, text=True)
    out_data = json.loads(result.stdout.strip().split("\n")[-1])

    if out_data.get("status") == "error":
        raise Exception(f"Blender preview failed: {out_data.get('error')}")

    logger.info(f"Preview job {job_id} complete. Output at {out_data['mesh_path']}")
    return out_data['mesh_path']

def process_export(job_id: str, gpx_path: str, output_path: str, format: str, settings: dict):
    logger.info(f"Starting export job {job_id} for {gpx_path} in {format}")
    cmd_python = [
        "python", "-m", "trailprint3d_backend.blender_runner",
        "export", job_id, gpx_path, output_path, format, json.dumps(settings)
    ]
    result = subprocess.run(cmd_python, check=True, capture_output=True, text=True)
    out_data = json.loads(result.stdout.strip().split("\n")[-1])

    if out_data.get("status") == "error":
        raise Exception(f"Blender export failed: {out_data.get('error')}")

    logger.info(f"Export job {job_id} complete. Output at {out_data['mesh_path']}")
    return out_data['mesh_path']

if __name__ == '__main__':
    from rq import Connection
    with Connection(redis_conn):
        worker = Worker(['default'])
        worker.work()
