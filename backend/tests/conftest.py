"""Shared pytest fixtures."""
import os

import pytest


@pytest.fixture(autouse=True)
def set_test_env(tmp_path, monkeypatch):
    """Point all path config to a temp directory for isolation."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    # Reset settings singleton so it re-reads env
    import backend.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_settings", None)
