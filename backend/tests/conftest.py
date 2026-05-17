"""Shared pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def set_test_env(tmp_path, monkeypatch):
    """Point all path config to a temp directory for isolation."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    # Clear the lru_cache so get_settings() re-reads the patched env vars
    import backend.config as cfg_mod
    cfg_mod.get_settings.cache_clear()
    yield
    # Clear again after the test to avoid cross-test contamination
    cfg_mod.get_settings.cache_clear()
