import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.documents import get_document
from app.db.models import Chunk, Section
from app.db.session import get_session

# Read-only views for the Database page.
router = APIRouter(prefix="/api")


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    heading: str
    level: int
    heading_path: str
    page_start: int
    page_end: int
    chunk_count: int = 0  # filled in by the list


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_in_section: int
    text: str
    context: str | None
    summary: str | None
    keywords: list[str] | None
    enriched: bool
    page_start: int
    page_end: int
    has_embedding: bool = False  # the vector itself is never sent, only whether it exists


@router.get("/documents/{document_id}/sections", response_model=list[SectionOut])
def list_sections(document_id: uuid.UUID, session: Session = Depends(get_session)):
    """Flat list in document order (parents before their children); `level` gives the indent."""
    get_document(document_id, session)
    chunk_counts = dict(
        session.execute(
            select(Chunk.section_id, func.count())
            .where(Chunk.document_id == document_id)
            .group_by(Chunk.section_id)
        ).all()
    )
    sections = session.scalars(
        select(Section).where(Section.document_id == document_id).order_by(Section.position)
    )
    return [
        SectionOut.model_validate(s).model_copy(update={"chunk_count": chunk_counts.get(s.id, 0)})
        for s in sections
    ]


@router.get("/sections/{section_id}/chunks", response_model=list[ChunkOut])
def list_chunks(section_id: uuid.UUID, session: Session = Depends(get_session)):
    if session.get(Section, section_id) is None:
        raise HTTPException(404, "Section not found.")
    chunks = session.scalars(
        select(Chunk).where(Chunk.section_id == section_id).order_by(Chunk.position_in_section)
    )
    return [
        ChunkOut.model_validate(c).model_copy(update={"has_embedding": c.embedding is not None})
        for c in chunks
    ]
