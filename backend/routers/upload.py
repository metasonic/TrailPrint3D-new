from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..models.schemas import TrackStats, UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_gpx(file: UploadFile = File(...)):
    cfg = get_settings()

    ext = Path(file.filename).suffix.lower()
    if ext not in (".gpx", ".igc"):
        raise HTTPException(status_code=400, detail="Only .gpx and .igc files are accepted")

    # Check size
    content = await file.read()
    max_bytes = cfg.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {cfg.MAX_UPLOAD_SIZE_MB} MB",
        )

    file_id = str(uuid.uuid4())
    dest = cfg.OUTPUT_DIR / "uploads" / f"{file_id}{ext}"
    dest.write_bytes(content)

    # Parse track stats
    try:
        from ..pipeline.gpx_parser import read_track_file, compute_track_stats

        segments = read_track_file(dest)
        raw_stats = compute_track_stats(segments)
        stats = TrackStats(
            point_count=raw_stats.point_count,
            length_km=raw_stats.length_km,
            elevation_gain_m=raw_stats.elevation_gain_m,
            min_lat=raw_stats.min_lat,
            max_lat=raw_stats.max_lat,
            min_lon=raw_stats.min_lon,
            max_lon=raw_stats.max_lon,
            date=raw_stats.date,
        )
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not parse track file: {exc}")

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        track_stats=stats,
    )
