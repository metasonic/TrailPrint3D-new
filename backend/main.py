from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import upload, preview, export

app = FastAPI(
    title="TrailPrint3D API",
    description="Convert GPX tracks into 3D-printable terrain meshes",
    version="1.0.0",
)

cfg = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(preview.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
