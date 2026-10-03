import json
import re

import pymupdf
import pytest
from sqlalchemy import select

from app.api.documents import file_path
from app.db.models import Chunk, Document, Section
from app.ingestion import enricher
from app.ingestion.enricher import SectionJob, enrich_section
from app.ingestion.parser import NoTextError, parse_pdf
from app.ingestion.pipeline import process_document
from app.ingestion.queue import DocumentQueue
from env.config import settings


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


def fake_haiku(monkeypatch, replies):
    """Replace the enrichment call; `replies(messages)` returns the text for each call. Returns the calls."""
    calls = []

    def complete(model, system, messages, max_tokens):
        calls.append(messages)
        return replies(messages)

    monkeypatch.setattr(enricher, "complete", complete)
    return calls


def good_reply(messages):
    """Valid JSON for the chunks listed in the second content block."""
    ids = re.findall(r"^\[(\d+)\]$", messages[0]["content"][1]["text"], re.M)
    entries = [
        {"id": int(i), "context": f"Context {i}.", "summary": f"Summary {i}.", "keywords": ["k1", "k2"]}
        for i in ids
    ]
    return json.dumps({"chunks": entries})


def test_enrichment_is_stored_and_the_context_is_embedded(session_factory, fake_embedder, monkeypatch):
    calls = fake_haiku(monkeypatch, good_reply)
    embedded = []

    def record(texts):
        embedded.extend(texts)
        return [[1.0, 0.0, 0.0, 0.0]] * len(texts)

    monkeypatch.setattr(fake_embedder, "embed", record)
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        document = session.get(Document, document_id)
        chunks = session.scalars(select(Chunk).order_by(Chunk.position_in_document)).all()
        assert document.status == "ready"
        assert document.chunks_done == document.chunk_count == len(chunks) > 0
        assert all(c.enriched and c.summary.startswith("Summary") and c.keywords == ["k1", "k2"] for c in chunks)
        assert embedded == [f"{c.context}\n\n{c.text}" for c in chunks]
    first_block = calls[0][0]["content"][0]
    assert first_block["cache_control"] == {"type": "ephemeral"}
    assert "Scope body text." in first_block["text"]  # the whole document


def test_json_in_a_code_fence_is_accepted(session_factory, monkeypatch):
    fake_haiku(monkeypatch, lambda m: "```json\n" + good_reply(m) + "\n```")
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        assert all(c.enriched for c in session.scalars(select(Chunk)))


def test_one_invalid_reply_is_retried(session_factory, monkeypatch):
    replies = iter(["not json"])
    calls = fake_haiku(monkeypatch, lambda m: next(replies, None) or good_reply(m))
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        assert all(c.enriched for c in session.scalars(select(Chunk)))
    assert len(calls) == 4  # three sections, plus the one retry


def test_invalid_json_twice_stores_chunks_unenriched_and_the_document_is_ready(
    session_factory, fake_embedder, monkeypatch
):
    fake_haiku(monkeypatch, lambda m: "sorry, no JSON here")
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        document = session.get(Document, document_id)
        chunks = session.scalars(select(Chunk)).all()
        assert document.status == "ready"
        assert document.chunks_done == document.chunk_count > 0
        assert all(not c.enriched and c.summary is None and c.embedding is not None for c in chunks)


def test_a_reply_with_missing_chunk_ids_counts_as_invalid(session_factory, monkeypatch):
    fake_haiku(monkeypatch, lambda m: json.dumps({"chunks": []}))
    document_id = store(session_factory, pdf_with_headings())

    process_document(session_factory, document_id)

    with session_factory() as session:
        assert not any(c.enriched for c in session.scalars(select(Chunk)))


def test_long_sections_are_sent_in_groups(monkeypatch):
    calls = fake_haiku(monkeypatch, good_reply)
    monkeypatch.setattr(settings, "ENRICH_BATCH_SIZE", 2)

    results = enrich_section("the document", SectionJob("1 A", "section", ["a", "b", "c", "d", "e"]))

    assert len(calls) == 3
    assert all(r is not None for r in results) and len(results) == 5


def test_a_document_over_the_window_sends_the_section_instead(monkeypatch):
    calls = fake_haiku(monkeypatch, good_reply)
    monkeypatch.setattr(settings, "ENRICH_DOC_MAX_TOKENS", 1)

    enrich_section("the whole document", SectionJob("1 A", "just the section", ["a"]))

    assert "just the section" in calls[0][0]["content"][0]["text"]
    assert "whole document" not in calls[0][0]["content"][0]["text"]
