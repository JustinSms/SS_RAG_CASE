"""Load the PDFs in eval/pdfs through the real ingestion pipeline (A3-A8) and export their heading trees.

The heading trees (eval/trees/<pdf>.txt, one heading path per line) are what the gold headings in
the question files are picked from.

    docker compose --profile eval run --rm eval python ingest.py
"""

import hashlib
import logging
import shutil
from pathlib import Path

from sqlalchemy import select

from app.api.documents import file_path
from app.db.models import Document, Section
from app.ingestion.pipeline import process_document
from eval.db import ensure_database

EVAL_DIR = Path(__file__).parent
PDF_DIR = EVAL_DIR / "pdfs"
TREE_DIR = EVAL_DIR / "trees"

log = logging.getLogger(__name__)


def ingest_pdf(session_factory, pdf: Path) -> None:
    """One PDF. Skipped if the same file is already ready; a changed file with the same name replaces the old one."""
    content = pdf.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    with session_factory() as session:
        for old in session.scalars(select(Document).where(Document.filename == pdf.name)):
            if old.sha256 == sha256 and old.status == "ready":
                log.info("%s is already ingested", pdf.name)
                return
            file_path(old.id).unlink(missing_ok=True)
            session.delete(old)
        document = Document(filename=pdf.name, sha256=sha256, size_bytes=len(content))
        session.add(document)
        session.commit()
        document_id = document.id

    file_path(document_id).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, file_path(document_id))
    log.info("ingesting %s", pdf.name)
    try:
        process_document(session_factory, document_id)
    except Exception:
        with session_factory() as session:
            session.delete(session.get(Document, document_id))
            session.commit()
        raise


def export_trees(session_factory, folder: Path) -> list[Path]:
    """One text file per ready document: its heading paths in document order."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    with session_factory() as session:
        for document in session.scalars(select(Document).where(Document.status == "ready").order_by(Document.filename)):
            paths = session.scalars(
                select(Section.heading_path).where(Section.document_id == document.id).order_by(Section.position)
            ).all()
            target = folder / f"{document.filename}.txt"
            target.write_text("\n".join(paths) + "\n")
            written.append(target)
    return written


def ingest_all(session_factory, pdf_folder: Path = PDF_DIR, tree_folder: Path = TREE_DIR) -> list[Path]:
    pdfs = sorted(pdf_folder.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs in {pdf_folder}.")
    for pdf in pdfs:
        ingest_pdf(session_factory, pdf)
    return export_trees(session_factory, tree_folder)


if __name__ == "__main__":
    from app.db.session import SessionLocal
    from app.retrieval.embedder import get_embedder

    logging.basicConfig(level=logging.INFO)
    ensure_database()
    get_embedder()
    for tree in ingest_all(SessionLocal):
        print(f"heading tree: {tree.relative_to(EVAL_DIR.parent)}")
