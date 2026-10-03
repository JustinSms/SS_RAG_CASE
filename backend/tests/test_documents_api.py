import uuid
from pathlib import Path

from app.db.models import Chunk, Document, Section
from env.config import settings
from tests.conftest import make_pdf


def upload(client, *pdfs, names=None):
    names = names or [f"doc{i}.pdf" for i in range(len(pdfs))]
    files = [("files", (name, pdf, "application/pdf")) for name, pdf in zip(names, pdfs)]
    return client.post("/api/documents", files=files)


def test_upload_returns_202_and_document_becomes_ready(client):
    response = upload(client, make_pdf("one"))
    assert response.status_code == 202
    client.app.state.queue.join()

    documents = client.get("/api/documents").json()
    assert [d["id"] for d in documents] == response.json()["ids"]
    assert documents[0]["status"] == "ready"
    assert documents[0]["filename"] == "doc0.pdf"


def test_upload_several_files(client):
    response = upload(client, make_pdf("one"), make_pdf("two"))
    assert response.status_code == 202
    assert len(response.json()["ids"]) == 2


def test_same_file_again_returns_409_with_existing_document(client):
    pdf = make_pdf()
    first = upload(client, pdf).json()["ids"][0]
    response = upload(client, pdf, names=["renamed.pdf"])
    assert response.status_code == 409
    assert response.json()["document"]["id"] == first
    assert len(client.get("/api/documents").json()) == 1


def test_same_file_twice_in_one_request_returns_409(client):
    pdf = make_pdf()
    assert upload(client, pdf, pdf).status_code == 409
    assert client.get("/api/documents").json() == []


def test_too_large_returns_413(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    assert upload(client, make_pdf()).status_code == 413


def test_not_a_pdf_returns_415(client):
    response = upload(client, b"just some text", names=["notes.pdf"])
    assert response.status_code == 415


def test_broken_pdf_returns_415(client):
    assert upload(client, b"%PDF-1.7 garbage").status_code == 415


def test_encrypted_pdf_returns_415(client):
    response = upload(client, make_pdf(password="secret"))
    assert response.status_code == 415
    assert "encrypted" in response.json()["detail"]


def test_one_bad_file_rejects_the_whole_request(client):
    assert upload(client, make_pdf(), b"nope").status_code == 415
    assert client.get("/api/documents").json() == []


def test_download_file(client):
    pdf = make_pdf()
    document_id = upload(client, pdf).json()["ids"][0]
    response = client.get(f"/api/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.content == pdf
    assert response.headers["content-type"] == "application/pdf"


def test_delete_removes_row_and_file(client):
    document_id = upload(client, make_pdf()).json()["ids"][0]
    client.app.state.queue.join()
    assert client.delete(f"/api/documents/{document_id}").status_code == 204
    assert client.get("/api/documents").json() == []
    assert client.get(f"/api/documents/{document_id}/file").status_code == 404
    assert not list(Path(settings.UPLOADS_DIR).glob("*.pdf"))


def test_delete_unknown_document_returns_404(client):
    assert client.delete("/api/documents/00000000-0000-0000-0000-000000000000").status_code == 404


def test_delete_cascades_to_sections_and_chunks(client, session_factory):
    document_id = uuid.UUID(upload(client, make_pdf()).json()["ids"][0])
    client.app.state.queue.join()
    with session_factory() as session:
        section = Section(document_id=document_id, heading="1 Intro", level=1,
                          heading_path="1 Intro", position=0, page_start=1, page_end=1)
        session.add(section)
        session.flush()
        session.add(Chunk(document_id=document_id, section_id=section.id, position_in_section=0,
                          position_in_document=0, text="x", page_start=1, page_end=1))
        session.commit()

    client.delete(f"/api/documents/{document_id}")

    with session_factory() as session:
        assert session.query(Document).count() == 0
        assert session.query(Section).count() == 0
        assert session.query(Chunk).count() == 0

