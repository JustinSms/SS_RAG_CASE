import hashlib
import uuid
from datetime import datetime
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.session import get_session
from env.config import settings

router = APIRouter(prefix="/api/documents")

PDF_HEADER = b"%PDF"
BYTES_PER_MB = 1024 * 1024
# An overwrite is ingested under "<sha256>:pending:<id>" because the old version still holds the
# real hash (it is unique). The pipeline swaps the real hash in when the new version is ready.
PENDING_MARKER = ":pending:"


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size_bytes: int
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int | None
    chunks_done: int
    created_at: datetime


def file_path(document_id: uuid.UUID) -> Path:
    return Path(settings.UPLOADS_DIR) / f"{document_id}.pdf"


def check_pdf(name: str, content: bytes) -> None:
    """A1: header, size and encryption. Raises HTTPException with 413 or 415."""
    if len(content) > settings.MAX_UPLOAD_MB * BYTES_PER_MB:
        raise HTTPException(413, f"{name} is larger than {settings.MAX_UPLOAD_MB} MB.")
    if not content.startswith(PDF_HEADER):
        raise HTTPException(415, f"{name} is not a PDF.")
    try:
        encrypted = pymupdf.open(stream=content, filetype="pdf").needs_pass
    except Exception:
        raise HTTPException(415, f"{name} is not a readable PDF.")
    if encrypted:
        raise HTTPException(415, f"{name} is encrypted. Remove the password and upload again.")


@router.post("", status_code=202)
async def upload(
    files: list[UploadFile],
    request: Request,
    overwrite: bool = False,
    session: Session = Depends(get_session),
):
    # Check every file before storing any, so a bad one rejects the whole request.
    checked: list[tuple[str, bytes, str, bool]] = []
    for upload_file in files:
        name = Path(upload_file.filename or "document.pdf").name
        # Read one byte past the limit: enough to detect "too large" without loading more.
        content = await upload_file.read(settings.MAX_UPLOAD_MB * BYTES_PER_MB + 1)
        check_pdf(name, content)
        sha256 = hashlib.sha256(content).hexdigest()
        existing = session.scalar(select(Document).where(Document.sha256 == sha256))
        repeated_in_request = any(sha256 == c[2] for c in checked)
        if repeated_in_request or (existing is not None and not overwrite):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": f"{name} is already uploaded.",
                    "document": DocumentOut.model_validate(existing).model_dump(mode="json")
                    if existing
                    else None,
                },
            )
        checked.append((name, content, sha256, existing is not None))

    documents = []
    for name, content, sha256, replaces_existing in checked:
        document_id = uuid.uuid4()
        stored_hash = f"{sha256}{PENDING_MARKER}{document_id}" if replaces_existing else sha256
        document = Document(id=document_id, filename=name, sha256=stored_hash, size_bytes=len(content))
        session.add(document)
        session.flush()
        path = file_path(document.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        documents.append(document)
    session.commit()

    for document in documents:
        request.app.state.queue.enqueue(document.id)
    return {"ids": [str(d.id) for d in documents]}


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)):
    return session.scalars(select(Document).order_by(Document.created_at.desc())).all()


def get_document(document_id: uuid.UUID, session: Session) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, session: Session = Depends(get_session)):
    document = get_document(document_id, session)
    session.delete(document)  # sections and chunks go with it (ON DELETE CASCADE)
    session.commit()
    file_path(document_id).unlink(missing_ok=True)


@router.get("/{document_id}/file")
def download_file(document_id: uuid.UUID, session: Session = Depends(get_session)):
    document = get_document(document_id, session)
    path = file_path(document_id)
    if not path.exists():
        raise HTTPException(404, "The file is missing on the server.")
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",  # opens in the browser at the cited page
        filename=document.filename,
    )
