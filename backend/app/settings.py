"""Environment-variable-driven runtime config, validated at startup."""

from pathlib import Path

from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    redis_url: RedisDsn = Field(default="redis://redis:6379/0")  # type: ignore[assignment]
    output_dir: Path = Field(default=Path("/app/output"))
    max_upload_size_mb: int = Field(default=10, gt=0, le=1024)
    elevation_cache_dir: Path = Field(default=Path("/app/elevation_cache"))
    dem_resolution: int = Field(default=30)
    max_dem_download_mb: int = Field(default=100, gt=0, le=10_000)
    preview_timeout_seconds: int = Field(default=60, gt=0, le=3600)
    export_timeout_seconds: int = Field(default=300, gt=0, le=3600)
    celery_worker_concurrency: int = Field(default=4, gt=0, le=64)
    flower_enabled: bool = Field(default=False)

    def model_post_init(self, _: object) -> None:
        if self.dem_resolution not in (30, 90):
            raise ValueError("DEM_RESOLUTION must be 30 or 90")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.elevation_cache_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "uploads").mkdir(parents=True, exist_ok=True)


settings = Settings()
