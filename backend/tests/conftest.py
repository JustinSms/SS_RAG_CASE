import pytest
from fastapi.testclient import TestClient

from app import health, main


@pytest.fixture
def make_client(monkeypatch):
    """Build a client with a fake key check, a fake DB check and fake memory."""

    def build(key_status="ok", db_ok=True, memory_gb=16.0):
        monkeypatch.setattr(main, "check_api_key", lambda: key_status)
        monkeypatch.setattr(health, "check_db", lambda: db_ok)
        monkeypatch.setattr(health, "total_memory_gb", lambda: memory_gb)
        return TestClient(main.app)

    return build
