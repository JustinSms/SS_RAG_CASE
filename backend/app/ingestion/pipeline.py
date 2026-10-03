import uuid

from sqlalchemy import select

from app.api.documents import PENDING_MARKER, file_path
from app.db.models import Chunk, Document, Section
from app.ingestion.chunker import chunk_section
from app.ingestion.enricher import SectionJob, enrich_sections
from app.ingestion.parser import parse_pdf
from app.ingestion.sections import build_sections
from app.retrieval.embedder import get_embedder


def replace_old_version(session, document) -> uuid.UUID | None:
    """Overwrite: drop the old version and take over its hash. Returns the old id, if any.

    Runs in the same transaction as marking the new document ready.
    """
    if PENDING_MARKER not in document.sha256:
        return None
    real_hash = document.sha256.split(PENDING_MARKER)[0]
    old = session.scalar(select(Document).where(Document.sha256 == real_hash))
    old_id = old.id if old is not None else None
    if old is not None:
        session.delete(old)  # sections and chunks go with it (ON DELETE CASCADE)
        session.flush()  # the delete must reach the database before the hash is reused
    document.sha256 = real_hash
    return old_id


def process_document(session_factory, document_id) -> None:
    """A3-A8 for one document."""
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None:  # deleted while it was waiting in the queue
            return

        pages = parse_pdf(str(file_path(document_id)))  # A3
        drafts = build_sections(pages)  # A4

        ids = {draft.position: uuid.uuid4() for draft in drafts}
        position_in_document = 0
        chunks = []
        jobs = []  # one per section with chunks, for A6
        job_chunks = []
        for draft in drafts:  # A5, A8
            session.add(
                Section(
                    id=ids[draft.position],
                    document_id=document.id,
                    parent_id=ids.get(draft.parent),
                    heading=draft.heading,
                    level=draft.level,
                    heading_path=draft.heading_path,
                    position=draft.position,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                )
            )
            session.flush()  # a section row must exist before its children and chunks
            section_chunks = []
            for position_in_section, chunk in enumerate(chunk_section(draft.paragraphs)):
                row = Chunk(
                    document_id=document.id,
                    section_id=ids[draft.position],
                    position_in_section=position_in_section,
                    position_in_document=position_in_document,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
                session.add(row)
                chunks.append(row)
                section_chunks.append(row)
                position_in_document += 1
            if section_chunks:
                text = "\n\n".join(p.text for p in draft.paragraphs)
                jobs.append(SectionJob(draft.heading_path, text, [c.text for c in section_chunks]))
                job_chunks.append(section_chunks)

        document.chunk_count = position_in_document
        session.commit()

        def section_done(index):  # progress bar: runs in this thread, as each section finishes
            document.chunks_done += len(job_chunks[index])
            session.commit()

        document_text = "\n\n".join(page.markdown for page in pages)
        enriched = enrich_sections(document_text, jobs, section_done)  # A6
        for section_chunks, results in zip(job_chunks, enriched):
            for chunk, result in zip(section_chunks, results):
                if result is not None:
                    chunk.context, chunk.summary = result.context, result.summary
                    chunk.keywords, chunk.enriched = result.keywords, True

        texts = [f"{c.context}\n\n{c.text}" if c.context else c.text for c in chunks]
        vectors = get_embedder().embed(texts)  # A7
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector

        document.page_count = len(pages)
        document.status = "ready"
        old_id = replace_old_version(session, document)
        session.commit()
        if old_id is not None:
            file_path(old_id).unlink(missing_ok=True)
