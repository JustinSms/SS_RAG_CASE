"""B2: cosine search over the chunks of ready documents."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, Section
from env.config import settings

log = logging.getLogger(__name__)

SCORES_LOGGED = 5


@dataclass
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    filename: str
    heading_path: str
    text: str
    page_start: int
    page_end: int
    position_in_document: int
    similarity: float  # 0 for chunks that were not found by the search (see load_section_chunks)
    rerank: float | None = None  # B3: set by the reranker; None if it failed or the chunk was selected
    summary: str | None = None
    keywords: list[str] | None = None


def to_hit(chunk: Chunk, heading_path: str, filename: str, similarity: float) -> Hit:
    return Hit(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        section_id=chunk.section_id,
        filename=filename,
        heading_path=heading_path,
        text=chunk.text,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        position_in_document=chunk.position_in_document,
        similarity=similarity,
        summary=chunk.summary,
        keywords=chunk.keywords,
    )


def search_chunks(session: Session, vector: list[float]) -> list[Hit]:
    """The closest chunks with similarity >= SIMILARITY_CUTOFF, best first, at most MAX_CANDIDATES."""
    distance = Chunk.embedding.cosine_distance(vector)
    rows = session.execute(
        select(Chunk, Section.heading_path, Document.filename, distance)
        .join(Section, Chunk.section_id == Section.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.status == "ready")
        .order_by(distance)
        .limit(settings.MAX_CANDIDATES)
    ).all()

    hits = [to_hit(chunk, heading_path, filename, 1 - dist) for chunk, heading_path, filename, dist in rows]
    # Logged before the cutoff, so a question that finds nothing still shows its best scores.
    log.info("best cosine scores: %s", [round(h.similarity, 3) for h in hits[:SCORES_LOGGED]])
    return [h for h in hits if h.similarity >= settings.SIMILARITY_CUTOFF]


def load_section_chunks(session: Session, section_ids: list[uuid.UUID]) -> list[Hit]:
    """Every chunk of the given sections, in document order."""
    rows = session.execute(
        select(Chunk, Section.heading_path, Document.filename)
        .join(Section, Chunk.section_id == Section.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.section_id.in_(section_ids))
        .order_by(Document.filename, Chunk.document_id, Chunk.position_in_document)
    ).all()
    return [to_hit(chunk, heading_path, filename, 0.0) for chunk, heading_path, filename in rows]
