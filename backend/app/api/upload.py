from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from ..config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {"gpx", "igc"}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_gpx(file: UploadFile) -> dict:
    """
    Accept a GPX or IGC file upload.

    Returns ``{"upload_id": "<uuid>", "filename": "<original name>"}``
    so the client can reference the file when submitting a job.
    """
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    upload_id = str(uuid.uuid4())
    dest = Path(settings.UPLOAD_DIR) / f"{upload_id}.{ext}"

    dest.parent.mkdir(parents=True, exist_ok=True)

    bytes_written = 0
    try:
        with dest.open("wb") as fh:
            while True:
                chunk = await file.read(65536)  # 64 KiB chunks
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File exceeds the maximum allowed size of "
                            f"{settings.MAX_UPLOAD_MB} MB."
                        ),
                    )
                fh.write(chunk)
    finally:
        await file.close()

    return {"upload_id": upload_id, "filename": file.filename}
