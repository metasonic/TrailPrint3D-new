from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import export, health, jobs, preview


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure output directory exists before serving static files
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="TrailPrint3D API",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve generated files (GLB, STL, OBJ, 3MF) directly from the output volume
app.mount(
    "/files",
    StaticFiles(directory=settings.output_dir, check_dir=False),
    name="files",
)

app.include_router(preview.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
