from __future__ import annotations

import json
import logging
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Extensions that should be downloaded as attachments vs. inline preview.
_ATTACHMENT_SUFFIXES = {".stl", ".obj", ".mtl", ".3mf"}
_INLINE_SUFFIXES = {".glb"}
_ALLOWED_SUFFIXES = _ATTACHMENT_SUFFIXES | _INLINE_SUFFIXES

_CONTENT_TYPES: dict[str, str] = {
    ".stl": "model/stl",
    ".obj": "model/obj",
    ".mtl": "model/mtl",
    ".3mf": "model/3mf",
    ".glb": "model/gltf-binary",
}


@router.get("/jobs/{job_id}/files/{filename}")
async def download_file(job_id: str, filename: str) -> FileResponse:
    """
    Stream a generated output file to the client.

    - STL, OBJ, MTL, 3MF → ``Content-Disposition: attachment``
    - GLB                 → ``Content-Disposition: inline``

    Returns 404 when the job or file does not exist, 403 when the requested
    file type is not in the allowed list.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"File type '{suffix}' is not allowed for download. "
                f"Allowed types: {sorted(_ALLOWED_SUFFIXES)}"
            ),
        )

    # Verify the job exists in Redis.
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw = await r.get(f"job:{job_id}")
    finally:
        await r.aclose()

    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    state = json.loads(raw)

    # Verify the file is listed in the job's output files list (prevents
    # path-traversal requests for arbitrary filenames).
    allowed_files: list[str] = state.get("files", [])
    if filename not in allowed_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{filename}' not found in job '{job_id}'.",
        )

    file_path = Path(settings.OUTPUT_DIR) / job_id / filename
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{filename}' does not exist on disk for job '{job_id}'.",
        )

    content_type = _CONTENT_TYPES.get(suffix, "application/octet-stream")

    if suffix in _INLINE_SUFFIXES:
        disposition = f"inline; filename=\"{filename}\""
    else:
        disposition = f"attachment; filename=\"{filename}\""

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        headers={"Content-Disposition": disposition},
        filename=filename,
    )
