from app.db.models import Document
from app.ingestion.queue import INTERRUPTED_MESSAGE, DocumentQueue, recover_interrupted


def add_document(session_factory, name, status):
    with session_factory() as session:
        document = Document(filename=name, sha256=name, size_bytes=1, status=status)
        session.add(document)
        session.commit()
        return document.id


def status_of(session_factory, document_id):
    with session_factory() as session:
        document = session.get(Document, document_id)
        return document.status, document.error


def test_startup_marks_interrupted_documents_failed(session_factory):
    stuck = add_document(session_factory, "stuck", "processing")
    done = add_document(session_factory, "done", "ready")

    recover_interrupted(session_factory)

    assert status_of(session_factory, stuck) == ("failed", INTERRUPTED_MESSAGE)
    assert status_of(session_factory, done) == ("ready", None)


def test_queue_processes_one_document_at_a_time_in_order(session_factory):
    seen = []
    queue = DocumentQueue(session_factory, process=lambda _, document_id: seen.append(document_id))
    queue.start()
    queue.enqueue("a")
    queue.enqueue("b")
    queue.join()
    queue.stop()
    assert seen == ["a", "b"]


def test_a_crash_marks_the_document_failed_and_the_queue_continues(session_factory):
    bad = add_document(session_factory, "bad", "processing")
    good = add_document(session_factory, "good", "processing")

    def process(_, document_id):
        if document_id == bad:
            raise RuntimeError("boom")
        with session_factory() as session:
            session.get(Document, document_id).status = "ready"
            session.commit()

    queue = DocumentQueue(session_factory, process=process)
    queue.start()
    queue.enqueue(bad)
    queue.enqueue(good)
    queue.join()
    queue.stop()

    assert status_of(session_factory, bad) == ("failed", "boom")
    assert status_of(session_factory, good)[0] == "ready"
