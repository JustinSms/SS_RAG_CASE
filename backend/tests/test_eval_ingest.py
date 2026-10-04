import pytest
from sqlalchemy import select

from app.db.models import Chunk, Document
from eval import ingest

from tests.conftest import make_pdf


@pytest.fixture
def pdf_folder(tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    (folder / "notes.pdf").write_bytes(make_pdf("The notice period is thirty days."))
    return folder


def test_a_pdf_goes_through_the_real_pipeline_and_its_tree_is_exported(session_factory, pdf_folder, tmp_path):
    trees = ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")

    with session_factory() as session:
        document = session.scalar(select(Document))
        assert document.filename == "notes.pdf" and document.status == "ready"
        assert session.scalars(select(Chunk)).all()
    assert [t.name for t in trees] == ["notes.pdf.txt"]
    assert trees[0].read_text().strip()  # at least one heading path


def test_ingesting_twice_does_not_repeat_the_work(session_factory, pdf_folder, tmp_path):
    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")
    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")

    with session_factory() as session:
        assert len(session.scalars(select(Document)).all()) == 1


def test_a_changed_pdf_replaces_the_old_version(session_factory, pdf_folder, tmp_path):
    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")
    (pdf_folder / "notes.pdf").write_bytes(make_pdf("The notice period is sixty days."))

    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")

    with session_factory() as session:
        assert [c.text for c in session.scalars(select(Chunk))] == ["The notice period is sixty days."]


def test_an_empty_folder_stops_with_a_message(session_factory, tmp_path):
    with pytest.raises(SystemExit, match="No PDFs"):
        ingest.ingest_all(session_factory, tmp_path, tmp_path / "trees")


def test_each_pdf_prints_a_progress_line(session_factory, pdf_folder, tmp_path, capsys):
    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")
    first = capsys.readouterr().out
    ingest.ingest_all(session_factory, pdf_folder, tmp_path / "trees")
    second = capsys.readouterr().out

    assert "[1/1] notes.pdf: ingesting ..." in first
    assert "[1/1] notes.pdf: 1 sections, 1 chunks in 0:00 | elapsed" in first
    assert "[1/1] notes.pdf: already ingested, skipped" in second
