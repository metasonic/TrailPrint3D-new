"""Test fixtures. Pre-creates the env so backend.app.settings doesn't fail at import."""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tp3d-test-"))
os.environ.setdefault("OUTPUT_DIR", str(_TMP / "out"))
os.environ.setdefault("ELEVATION_CACHE_DIR", str(_TMP / "cache"))
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")
