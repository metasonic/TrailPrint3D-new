import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings
from .routers import upload, preview, export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("uploads", "preview", "exports", "jobs"):
        (cfg.OUTPUT_DIR / sub).mkdir(exist_ok=True)
    cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("elevation", "tiles", "osm"):
        (cfg.CACHE_DIR / sub).mkdir(exist_ok=True)
    # Initialize preview semaphore inside the running event loop.
    # Python 3.12+ requires asyncio primitives to be created inside an async
    # context; creating them at module import time (no loop) raises RuntimeError.
    preview._preview_semaphore = asyncio.Semaphore(4)
    yield
    await export.close_pool()


cfg = get_settings()

app = FastAPI(
    title="TrailPrint3D API",
    description="Convert GPX tracks into 3D-printable terrain meshes",
    version="1.0.0",
    lifespan=lifespan,
    # Disable interactive docs in production — they enumerate all endpoints
    docs_url="/docs" if cfg.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if cfg.ENVIRONMENT == "development" else None,
    openapi_url="/openapi.json" if cfg.ENVIRONMENT == "development" else None,
)


class _SecurityHeaders(BaseHTTPMiddleware):
    """Inject standard defensive security headers on every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # X-XSS-Protection is deprecated; set to 0 to avoid legacy browser quirks
        resp.headers["X-XSS-Protection"] = "0"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' blob: data:; "
            "connect-src 'self'; "
            "worker-src blob:; "
            "object-src 'none';"
        )
        resp.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=(), payment=()"
        # Re-read settings on every request so HSTS is correct even if settings
        # are cleared between tests (get_settings uses lru_cache; call get_settings()
        # here rather than capturing a module-level cfg to avoid stale values).
        if get_settings().ENVIRONMENT != "development":
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp


app.add_middleware(_SecurityHeaders)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[cfg.FRONTEND_URL],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(upload.router)
app.include_router(preview.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    redis_ok = await export.check_redis()
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
