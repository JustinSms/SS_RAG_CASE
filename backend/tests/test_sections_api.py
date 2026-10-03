from app.db.models import Chunk, Document, Section

MISSING = "00000000-0000-0000-0000-000000000000"


def store_document(session_factory):
    """One document with two sections (the second inside the first); the first has two chunks."""
    with session_factory() as session:
        document = Document(filename="a.pdf", sha256="x", size_bytes=1, status="ready", chunk_count=3)
        session.add(document)
        session.flush()
        parent = Section(document_id=document.id, heading="1 Scope", level=1, heading_path="1 Scope",
                         position=0, page_start=1, page_end=2)
        session.add(parent)
        session.flush()
        child = Section(document_id=document.id, parent_id=parent.id, heading="1.1 Data", level=2,
                        heading_path="1 Scope > 1.1 Data", position=1, page_start=2, page_end=2)
        session.add(child)
        session.flush()

        def chunk(section, position, **fields):
            session.add(Chunk(document_id=document.id, section_id=section.id, position_in_section=position,
                              position_in_document=position, page_start=1, page_end=1, **fields))

        # Added out of order on purpose: the endpoint must sort by position.
        chunk(parent, 1, text="second", enriched=False)
        chunk(parent, 0, text="first", context="ctx", summary="sum", keywords=["a", "b"],
              enriched=True, embedding=[0.1, 0.2])
        chunk(child, 0, text="child text")
        session.commit()
        return document.id, parent.id, child.id


def test_sections_come_in_document_order_with_chunk_counts(client, session_factory):
    document_id, parent_id, child_id = store_document(session_factory)
    sections = client.get(f"/api/documents/{document_id}/sections").json()
    assert [(s["heading"], s["level"], s["chunk_count"]) for s in sections] == [
        ("1 Scope", 1, 2),
        ("1.1 Data", 2, 1),
    ]
    assert sections[1]["parent_id"] == str(parent_id)
    assert sections[1]["heading_path"] == "1 Scope > 1.1 Data"
    assert (sections[0]["page_start"], sections[0]["page_end"]) == (1, 2)


def test_document_list_has_section_count(client, session_factory):
    store_document(session_factory)
    assert client.get("/api/documents").json()[0]["section_count"] == 2


def test_sections_of_unknown_document_returns_404(client):
    assert client.get(f"/api/documents/{MISSING}/sections").status_code == 404


def test_chunks_come_in_order_with_enrichment_and_embedding_flags(client, session_factory):
    _, parent_id, _ = store_document(session_factory)
    chunks = client.get(f"/api/sections/{parent_id}/chunks").json()
    assert [c["text"] for c in chunks] == ["first", "second"]
    first, second = chunks
    assert (first["context"], first["summary"], first["keywords"]) == ("ctx", "sum", ["a", "b"])
    assert first["enriched"] is True and first["has_embedding"] is True
    assert second["enriched"] is False and second["has_embedding"] is False
    assert second["keywords"] is None


def test_chunks_never_include_the_vector(client, session_factory):
    _, parent_id, _ = store_document(session_factory)
    for chunk in client.get(f"/api/sections/{parent_id}/chunks").json():
        assert "embedding" not in chunk


def test_chunks_of_unknown_section_returns_404(client):
    assert client.get(f"/api/sections/{MISSING}/chunks").status_code == 404
