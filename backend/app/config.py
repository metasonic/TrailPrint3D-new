from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    output_dir: str = "/app/output"
    blender_executable: str = "/usr/bin/blender"
    blender_script_path: str = "/app/scripts/generate_terrain.py"
    max_upload_size_mb: int = 10
    elevation_data_source: str = "mapzen"
    preview_timeout_seconds: int = 120
    export_timeout_seconds: int = 600
    celery_worker_concurrency: int = 1
    flower_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
