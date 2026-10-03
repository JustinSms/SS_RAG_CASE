import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import health, main
from app.db.models import Base
from app.db.session import get_session
from env.config import settings


@pytest.fixture
def session_factory(monkeypatch, tmp_path):
    """In-memory SQLite instead of Postgres, and a temp uploads folder."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")  # SQLite ignores ON DELETE otherwise

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)

    def override_session():
        with factory() as session:
            yield session

    main.app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "create_tables", lambda: None)
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    yield factory
    main.app.dependency_overrides.clear()


@pytest.fixture
def make_client(monkeypatch, session_factory):
    """Build a client with a fake key check, a fake DB check and fake memory."""

    def build(key_status="ok", db_ok=True, memory_gb=16.0):
        monkeypatch.setattr(main, "check_api_key", lambda: key_status)
        monkeypatch.setattr(health, "check_db", lambda: db_ok)
        monkeypatch.setattr(health, "total_memory_gb", lambda: memory_gb)
        return TestClient(main.app)

    return build


@pytest.fixture
def client(make_client):
    with make_client() as client:
        yield client


def make_pdf(text="Hello", password=None) -> bytes:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    if password:
        return document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password
        )
    return document.tobytes()
