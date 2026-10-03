import pymupdf
import pytest
from sqlalchemy import select

from app.api.documents import file_path
from app.db.models import Chunk, Document, Section
from app.ingestion.parser import NoTextError, parse_pdf
from app.ingestion.pipeline import process_document
from app.ingestion.queue import DocumentQueue


def pdf_with_headings() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Intro", fontsize=24)
    page.insert_text((72, 120), "Intro body text.", fontsize=11)
    page.insert_text((72, 160), "1.1 Aim", fontsize=16)
    page.insert_text((72, 200), "Aim body text.", fontsize=11)
    page = document.new_page()
    page.insert_text((72, 72), "2 Scope", fontsize=24)
    page.insert_text((72, 120), "Scope body text.", fontsize=11)
    return document.tobytes()


def blank_pdf() -> bytes:
    document = pymupdf.open()
    document.new_page()
    return document.tobytes()


def store(session_factory, pdf: bytes):
    with session_factory() as session:
        document = Document(filename="a.pdf", sha256="a", size_bytes=len(pdf))
        session.add(document)
        session.commit()
        path = file_path(document.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf)
        return document.id


def test_parser_returns_markdown_per_page_with_page_numbers(session_factory):
    document_id = store(session_factory, pdf_with_headings())
    pages = parse_pdf(str(file_path(document_id)))

    assert [p.number for p in pages] == [1, 2]
    assert pages[0].markdown.startswith("#")
    assert "Scope body text." in pages[1].markdown


def test_parser_rejects_a_pdf_without_text(session_factory):
    document_id = store(session_factory, blank_pdf())
    with pytest.raises(NoTextError, match="No text found"):
        parse_pdf(str(file_path(document_id)))


def test_pipeline_stores_sections_and_chunks(session_factory):
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        document = session.get(Document, document_id)
        sections = session.scalars(select(Section).order_by(Section.position)).all()
        chunks = session.scalars(select(Chunk).order_by(Chunk.position_in_document)).all()

        assert (document.status, document.page_count) == ("ready", 2)
        assert document.chunk_count == len(chunks) > 0
        aim = next(s for s in sections if s.heading.endswith("Aim"))
        assert aim.parent_id is not None
        assert " > " in aim.heading_path
        assert [c.position_in_document for c in chunks] == list(range(len(chunks)))
        assert {c.section_id for c in chunks} <= {s.id for s in sections}
        assert any("Scope body text." in c.text and c.page_start == 2 for c in chunks)


def test_a_pdf_without_text_fails_with_a_clear_message(session_factory):
    document_id = store(session_factory, blank_pdf())
    queue = DocumentQueue(session_factory)
    queue.start()
    queue.enqueue(document_id)
    queue.join()
    queue.stop()

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document.status == "failed"
        assert "No text found" in document.error


def test_pipeline_embeds_every_chunk(session_factory):
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        chunks = session.scalars(select(Chunk)).all()
        assert chunks and all(c.embedding is not None for c in chunks)
