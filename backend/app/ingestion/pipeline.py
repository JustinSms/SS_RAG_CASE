import uuid

from app.api.documents import file_path
from app.db.models import Chunk, Document, Section
from app.ingestion.chunker import chunk_section
from app.ingestion.parser import parse_pdf
from app.ingestion.sections import build_sections


def process_document(session_factory, document_id) -> None:
    """A3-A5 and A8 for one document. Enrichment and embedding come in later milestones."""
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None:  # deleted while it was waiting in the queue
            return

        pages = parse_pdf(str(file_path(document_id)))  # A3
        drafts = build_sections(pages)  # A4

        ids = {draft.position: uuid.uuid4() for draft in drafts}
        position_in_document = 0
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
            for position_in_section, chunk in enumerate(chunk_section(draft.paragraphs)):
                session.add(
                    Chunk(
                        document_id=document.id,
                        section_id=ids[draft.position],
                        position_in_section=position_in_section,
                        position_in_document=position_in_document,
                        text=chunk.text,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                    )
                )
                position_in_document += 1

        document.page_count = len(pages)
        document.chunk_count = position_in_document
        document.status = "ready"
        session.commit()
