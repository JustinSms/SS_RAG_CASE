import logging
import queue
import threading

from sqlalchemy import update

from app.db.models import Document
from app.ingestion.pipeline import process_document

log = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Processing was interrupted, please re-upload."


def recover_interrupted(session_factory) -> None:
    """On startup: documents left in 'processing' were cut off by a restart."""
    with session_factory() as session:
        session.execute(
            update(Document)
            .where(Document.status == "processing")
            .values(status="failed", error=INTERRUPTED_MESSAGE)
        )
        session.commit()


class DocumentQueue:
    """In-process queue: one worker thread, one document at a time."""

    def __init__(self, session_factory, process=process_document):
        self.session_factory = session_factory
        self.process = process
        self._jobs: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._jobs.put(None)
        self._worker.join()

    def enqueue(self, document_id) -> None:
        self._jobs.put(document_id)

    def join(self) -> None:
        """Wait until everything queued so far is done (used by tests)."""
        self._jobs.join()

    def _run(self) -> None:
        while True:
            document_id = self._jobs.get()
            try:
                if document_id is None:
                    return
                self._process_one(document_id)
            finally:
                self._jobs.task_done()

    def _process_one(self, document_id) -> None:
        try:
            self.process(self.session_factory, document_id)
        except Exception as error:
            log.exception("Processing %s failed", document_id)
            with self.session_factory() as session:
                document = session.get(Document, document_id)
                if document is not None:
                    document.status = "failed"
                    document.error = str(error)
                    session.commit()
