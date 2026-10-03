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
    filename: str
    heading_path: str
    text: str
    page_start: int
    page_end: int
    position_in_document: int
    similarity: float


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

    hits = [
        Hit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            heading_path=heading_path,
            text=chunk.text,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            position_in_document=chunk.position_in_document,
            similarity=1 - dist,
        )
        for chunk, heading_path, filename, dist in rows
    ]
    # Logged before the cutoff, so a question that finds nothing still shows its best scores.
    log.info("best cosine scores: %s", [round(h.similarity, 3) for h in hits[:SCORES_LOGGED]])
    return [h for h in hits if h.similarity >= settings.SIMILARITY_CUTOFF]
