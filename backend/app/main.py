from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import download, jobs, sse, upload
from .config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TrailPrint3D API",
    description="Backend API for TrailPrint3D — convert GPX tracks into 3-D printable models.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sse.router, prefix="/api")
app.include_router(download.router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Startup: ensure data directories exist
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _create_data_dirs() -> None:
    for path_str in (settings.UPLOAD_DIR, settings.OUTPUT_DIR):
        path = Path(path_str)
        path.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured directory exists: %s", path)


# ---------------------------------------------------------------------------
# Serve React frontend (if built)
# ---------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    logger.info("Serving React build from %s", _FRONTEND_DIST)
    # Mount at "/" — must come *after* all API routes so the API is reachable.
    app.mount(
        "/",
        StaticFiles(directory=str(_FRONTEND_DIST), html=True),
        name="frontend",
    )
else:
    logger.info(
        "No frontend build found at %s — skipping static file mount.", _FRONTEND_DIST
    )
