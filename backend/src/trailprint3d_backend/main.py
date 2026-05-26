import os
import uuid
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job

from trailprint3d_backend.worker import process_preview, process_export

app = FastAPI(title="TrailPrint3D API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(redis_url)
q = Queue(connection=redis_conn)

UPLOAD_DIR = os.path.abspath(os.getenv('UPLOAD_DIR', '/tmp/trailprint3d_uploads'))
OUTPUT_DIR = os.path.abspath(os.getenv('OUTPUT_DIR', '/tmp/trailprint3d_outputs'))
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', '52428800')) # Default 50MB

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ExportRequest(BaseModel):
    gpx_filename: str
    format: str = "stl"
    shape: str = "circle"
    colorMode: bool = False
    roads: bool = False

class PreviewRequest(BaseModel):
    shape: str = "circle"
    colorMode: bool = False
    roads: bool = False

def is_safe_path(base_dir, target_path):
    base = os.path.abspath(base_dir)
    target = os.path.abspath(target_path)
    return os.path.commonpath([base, target]) == base

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/upload")
async def upload_gpx(request: Request, file: UploadFile = File(...)):
    if not file.filename.endswith('.gpx'):
        raise HTTPException(status_code=400, detail="Only GPX files are allowed")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.gpx"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    size = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="File too large")
                buffer.write(chunk)
    except BaseException as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise e

    return {"file_id": file_id, "filename": safe_filename}

@app.post("/preview/{file_id}")
async def generate_preview(file_id: str, req: PreviewRequest):
    safe_id = os.path.basename(file_id)
    gpx_path = os.path.join(UPLOAD_DIR, f"{safe_id}.gpx")
    if not os.path.exists(gpx_path):
        raise HTTPException(status_code=404, detail="GPX file not found")

    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_preview.glb")

    settings = req.model_dump()
    job = await asyncio.to_thread(q.enqueue, process_preview, job_id, gpx_path, output_path, settings, job_id=job_id)
    return {"job_id": job.get_id()}

@app.post("/export")
async def request_export(req: ExportRequest):
    safe_gpx_filename = os.path.basename(req.gpx_filename)
    gpx_path = os.path.join(UPLOAD_DIR, safe_gpx_filename)

    if not is_safe_path(UPLOAD_DIR, gpx_path):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not os.path.exists(gpx_path):
        raise HTTPException(status_code=404, detail="GPX file not found")

    if req.format not in ["stl", "obj", "3mf"]:
        raise HTTPException(status_code=400, detail="Invalid export format")

    job_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_export.{req.format}")

    settings = req.model_dump()
    job = await asyncio.to_thread(q.enqueue, process_export, job_id, gpx_path, output_path, req.format, settings, job_id=job_id)
    return {"job_id": job.get_id()}

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    try:
        job = await asyncio.to_thread(Job.fetch, job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.is_finished:
        return {"status": "finished", "result": job.result}
    elif job.is_failed:
        return {"status": "failed", "error": str(job.exc_info)}
    else:
        return {"status": "pending"}

@app.get("/download/{filename}")
async def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(OUTPUT_DIR, safe_filename)

    if not is_safe_path(OUTPUT_DIR, file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)
