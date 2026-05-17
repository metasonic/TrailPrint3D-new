from __future__ import annotations

from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Storage paths
    DATA_DIR: str = "/data"
    UPLOAD_DIR: str = ""
    OUTPUT_DIR: str = ""

    # Blender
    BLENDER_PATH: str = "/usr/local/bin/blender"
    # BLENDER_ADDON_DIR must be the PARENT of the TrailPrint3D package dir
    # so that `import TrailPrint3D` works inside the headless Blender script.
    BLENDER_ADDON_DIR: str = "/app"

    # Job settings
    JOB_TTL_HOURS: int = 24
    MAX_UPLOAD_MB: int = 50

    # External API keys / hosts
    OPENTOPOGRAPHY_KEY: str = ""
    OPENTOPODATA_SELF_HOSTED: str = ""

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context: object) -> None:
        # Derive UPLOAD_DIR / OUTPUT_DIR from DATA_DIR when not explicitly set.
        if not self.UPLOAD_DIR:
            object.__setattr__(self, "UPLOAD_DIR", f"{self.DATA_DIR}/uploads")
        if not self.OUTPUT_DIR:
            object.__setattr__(self, "OUTPUT_DIR", f"{self.DATA_DIR}/outputs")


settings = Settings()
