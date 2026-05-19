from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    REDIS_URL: str = "redis://redis:6379/0"
    OUTPUT_DIR: Path = Path("/app/data")
    BLENDER_EXECUTABLE_PATH: Path = Path("/opt/blender/blender")
    ELEVATION_DATA_SOURCE: str = "TERRAIN-TILES"
    TERRAIN_RESOLUTION: int = 4
    MAX_UPLOAD_SIZE_MB: int = 50
    OPENTOPODATA_URL: str = "https://api.opentopodata.org/v1/"
    OPENTOPOGRAPHY_API_KEY: str = ""
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    CACHE_DIR: Path = Path("/app/.cache")
    CACHE_MAX_AGE_HOURS: int = 720
    ELEVATION_CACHE_SIZE: int = 50000
    ADDON_SRC_DIR: Path = Path("/app/TrailPrint3D")
    FRONTEND_URL: str = "http://localhost:3000"
    # Set to "development" to enable /docs and /redoc endpoints
    ENVIRONMENT: str = "production"

    @field_validator("FRONTEND_URL")
    @classmethod
    def _validate_frontend_url(cls, v: str) -> str:
        if v == "*" or not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(
                "FRONTEND_URL must be an absolute http(s):// URL — wildcards are not allowed"
            )
        return v.rstrip("/")

    @field_validator("OVERPASS_URL", "OPENTOPODATA_URL")
    @classmethod
    def _validate_external_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Must be an http(s):// URL")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
