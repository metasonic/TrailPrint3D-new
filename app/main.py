from fastapi.staticfiles import StaticFiles

from fastapi import BackgroundTasks
import threading

import subprocess
import json
import re
from fastapi import HTTPException

def is_valid_uuid(val):
    return bool(re.match(r'^[a-fA-F0-9\-]{36}(_preview)?$', val))

def run_headless_process(config_dict, output_dir):
    modelname = config_dict.get('modelname', 'default')

    if not is_valid_uuid(modelname):
        raise ValueError("Invalid modelname format")

    # Save config to a JSON file securely
    config_file = f"{output_dir}/{modelname}_config.json"
    with open(config_file, "w") as f:
        json.dump(config_dict, f)

    script = f'''
import sys
sys.path.append("/app")
from app.headless import perform_generation
import json

with open("{config_file}", "r") as f:
    config = json.load(f)

perform_generation(config, "{output_dir}/")
'''
    script_file = f"{output_dir}/{modelname}_script.py"
    with open(script_file, "w") as f:
        f.write(script)

    subprocess.run(["python", script_file])

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uuid
import os
import shutil

app = FastAPI(title="TrailPrint3D Headless")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

class GenerateRequest(BaseModel):
    id: str
    settings: dict

@app.post("/upload")
async def upload_gpx(gpx_file: UploadFile = File(...)):
    if not gpx_file.filename.endswith(".gpx"):
        raise HTTPException(status_code=400, detail="Only GPX files are allowed")

    session_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOADS_DIR, f"{session_id}.gpx")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(gpx_file.file, buffer)

    return {"id": session_id}


@app.post("/preview")
async def generate_preview(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not is_valid_uuid(req.id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    config = req.settings
    config["file_path"] = os.path.join(UPLOADS_DIR, f"{req.id}.gpx")
    config["modelname"] = req.id + "_preview"
    # Sensible defaults for fast preview
    config["objSize"] = 50
    config["scaleElevation"] = config.get("scaleElevation", 1.0)
    config["minThickness"] = 2.0
    config["api"] = "OPENTOPODATA"
    config["dataset"] = "srtm30m"
    config["sMapInKm"] = 1.0

    def worker():
        run_headless_process(config, OUTPUTS_DIR)

    background_tasks.add_task(worker)
    return {"status": "preview_started", "job_id": config["modelname"]}


@app.post("/generate")
async def generate_model(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not is_valid_uuid(req.id):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    # This will trigger the bpy script logic

    # Setup config
    config = req.settings
    config["file_path"] = os.path.join(UPLOADS_DIR, f"{req.id}.gpx")
    config["modelname"] = req.id

    # We need to run it in a thread because bpy ops are blocking and not thread safe
    def worker():
        run_headless_process(config, OUTPUTS_DIR)

    background_tasks.add_task(worker)

    return {"status": "generation_started", "job_id": req.id}


@app.get("/download/{job_id}")
async def download_file(job_id: str, format: str = "stl"):
    if not is_valid_uuid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    if format not in ["stl", "obj", "3mf"]:
        raise HTTPException(status_code=400, detail="Invalid format")

    file_path = os.path.join(OUTPUTS_DIR, f"{job_id}.{format}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=f"trailprint3d_{job_id}.{format}")

@app.get("/formats")
async def list_formats():
    return ["stl", "obj", "3mf"]


app.mount('/', StaticFiles(directory='frontend', html=True), name='frontend')
