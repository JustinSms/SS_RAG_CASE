import pymupdf
import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import health, main
from app.db.models import Chunk, Document, Section
from app.retrieval.search import to_hit
from app.retrieval import pipeline
from eval import ingest, run
from eval.db import EvalBase
from app.ingestion import enricher
from app.retrieval import embedder, reranker, rewriter, selector
from app.db.models import Base
from app.db.session import get_session
from env.config import settings


class FakeEmbedder:
    """Stands in for bge-m3: a vector that depends on the text, no model needed."""

    def embed(self, texts):
        return [[float(len(t) % 7), 1.0, 0.0, 0.0] for t in texts]


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    """No test loads the real model."""
    fake = FakeEmbedder()
    monkeypatch.setattr(embedder, "_embedder", fake)
    return fake


class FakeReranker:
    """Stands in for the cross-encoder: every chunk scores well, so the order stays as given."""

    def score(self, question, texts):
        return [0.9 for _ in texts]


@pytest.fixture(autouse=True)
def fake_reranker(monkeypatch):
    fake = FakeReranker()
    monkeypatch.setattr(reranker, "_reranker", fake)
    return fake


@pytest.fixture(autouse=True)
def no_enrichment_calls(monkeypatch):
    """No test reaches Anthropic: enrichment, rewrite and selection fail and fall back. Tests that need replies replace this."""

    def refuse(*args, **kwargs):
        raise RuntimeError("no network in tests")

    monkeypatch.setattr(enricher, "complete", refuse)
    monkeypatch.setattr(rewriter, "complete", refuse)
    monkeypatch.setattr(selector, "complete", refuse)


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


@pytest.fixture
def eval_session(session_factory, tmp_path, monkeypatch):
    """The test database with the eval tables added, a PDF ingested and a question file written."""
    engine = session_factory.kw["bind"].execution_options(schema_translate_map={"eval": None})
    EvalBase.metadata.create_all(engine)

    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "notes.pdf").write_bytes(make_pdf("The notice period is thirty days."))
    ingest.ingest_all(session_factory, pdfs, tmp_path / "trees")

    with session_factory() as session:
        heading = session.scalar(select(Section.heading_path))
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "notes.yaml").write_text(yaml.safe_dump([
        {"id": "n-01", "document": "notes.pdf", "question": "How long is the notice period?", "type": "single_fact",
         "answerable": True, "gold": [{"document": "notes.pdf", "heading": heading}]},
        {"id": "n-02", "document": "notes.pdf", "question": "And for the landlord?", "type": "follow_up",
         "answerable": True, "gold": [{"document": "notes.pdf", "heading": heading}],
         "history": [{"role": "user", "content": "How long is the notice period?"}]},
    ]))
    monkeypatch.setattr(run, "QUESTIONS_DIR", questions)

    def search(session, vector):  # pgvector's cosine search does not run on SQLite
        rows = session.execute(
            select(Chunk, Section.heading_path, Document.filename)
            .join(Section, Chunk.section_id == Section.id).join(Document, Chunk.document_id == Document.id)
        ).all()
        hits = [to_hit(c, path, name, 0.8) for c, path, name in rows]
        return [h for h in hits if h.similarity >= settings.SIMILARITY_CUTOFF]

    monkeypatch.setattr(pipeline, "search_chunks", search)
    with sessionmaker(engine)() as session:
        yield session
