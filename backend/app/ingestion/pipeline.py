from app.db.models import Document


def process_document(session_factory, document_id) -> None:
    """A1-A8 for one document. Milestone 3: a stub that only marks it ready."""
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None:  # deleted while it was waiting in the queue
            return
        document.status = "ready"
        session.commit()
