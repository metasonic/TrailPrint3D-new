from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..models.schemas import TrackStats, UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger(__name__)

# Printable ASCII only, no path separators
_SAFE_NAME_RE = re.compile(r'[^\x20-\x7e]|[/\\<>:"|?*]')


def _sanitize_filename(name: str | None) -> str:
    if not name:
        return "upload"
    safe = _SAFE_NAME_RE.sub("_", Path(name).name)
    return safe[:255] or "upload"


@router.post("/upload", response_model=UploadResponse)
async def upload_gpx(file: UploadFile = File(...)):
    cfg = get_settings()

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".gpx", ".igc"):
        raise HTTPException(status_code=400, detail="Only .gpx and .igc files are accepted")

    max_bytes = cfg.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Stream-read with early abort instead of loading the entire body first
    chunks: list[bytes] = []
    total = 0
    async for chunk in file:
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {cfg.MAX_UPLOAD_SIZE_MB} MB",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    # Magic-byte check: GPX must open with XML; IGC must open with a record type letter
    if ext == ".gpx":
        header = content.lstrip()
        if not (header.startswith(b"<?xml") or header.startswith(b"<gpx")):
            raise HTTPException(status_code=422, detail="File does not appear to be a valid GPX (XML) file")
    elif ext == ".igc":
        if not content or content[0:1].upper() not in (b"A", b"B", b"H", b"I", b"J", b"C", b"L"):
            raise HTTPException(status_code=422, detail="File does not appear to be a valid IGC file")

    file_id = str(uuid.uuid4())
    dest = cfg.OUTPUT_DIR / "uploads" / f"{file_id}{ext}"
    dest.write_bytes(content)

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
        logger.exception("Failed to parse uploaded track file %s", file_id)
        raise HTTPException(status_code=422, detail="Could not parse track file — ensure it is a valid GPX or IGC")

    return UploadResponse(
        file_id=file_id,
        filename=_sanitize_filename(file.filename),
        track_stats=stats,
    )
