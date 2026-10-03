import pytest

from app.db.models import Chunk, Document, Section
from app.retrieval import selector
from app.retrieval.search import load_section_chunks, to_hit
from app.retrieval.selector import parse_selection, select_extra_chunks
from env.config import settings


@pytest.fixture
def section_of_four(session_factory):
    """One section with four chunks (the second has no summary), and a second section with one chunk."""
    with session_factory() as session:
        document = Document(filename="Contract.pdf", sha256="a", size_bytes=1, status="ready")
        session.add(document)
        session.flush()
        sections = [
            Section(document_id=document.id, heading=h, level=1, heading_path=h, position=i, page_start=1, page_end=3)
            for i, h in enumerate(["1 Terms", "2 Fees"])
        ]
        session.add_all(sections)
        session.flush()
        chunks = []
        for n, (section, text) in enumerate([(0, "A"), (0, "B"), (0, "C"), (0, "D"), (1, "E")]):
            chunks.append(
                Chunk(
                    document_id=document.id, section_id=sections[section].id, position_in_section=n,
                    position_in_document=n, text=f"Text {text}.", page_start=n + 1, page_end=n + 1,
                    summary=None if text == "B" else f"Summary {text}.",
                    keywords=None if text == "B" else [f"kw{text}"],
                )
            )
        session.add_all(chunks)
        session.commit()
        yield session, [to_hit(c, "1 Terms", "Contract.pdf", 0.8) for c in chunks]


def fake_sonnet(monkeypatch, reply):
    calls = []

    def complete(model, system, messages, max_tokens):
        calls.append({"model": model, "prompt": messages[0]["content"]})
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(selector, "complete", complete)
    return calls


def test_a_section_loads_all_its_chunks_in_document_order(section_of_four):
    session, hits = section_of_four

    chunks = load_section_chunks(session, [hits[0].section_id])

    assert [c.text for c in chunks] == ["Text A.", "Text B.", "Text C.", "Text D."]
    assert chunks[0].summary == "Summary A." and chunks[0].keywords == ["kwA"]


def test_the_selected_chunks_come_back_and_the_prompt_lists_summaries(section_of_four, monkeypatch):
    session, hits = section_of_four
    calls = fake_sonnet(monkeypatch, '{"chunks": [3, 4]}')

    extra = select_extra_chunks(session, "What are the terms?", [hits[0]])

    assert [c.text for c in extra] == ["Text C.", "Text D."]
    prompt = calls[0]["prompt"]
    assert calls[0]["model"] == settings.SELECT_MODEL
    assert "What are the terms?" in prompt
    assert "[1] (kept, p. 1) Summary: Summary A. Keywords: kwA" in prompt
    assert "[2] (not kept, p. 2) Text: Text B." in prompt  # no summary: the start of the text
    assert "Text E." not in prompt and "2 Fees" not in prompt  # sections of chunks that were not kept stay out


def test_kept_chunks_unknown_numbers_and_duplicates_are_ignored(section_of_four, monkeypatch):
    session, hits = section_of_four
    fake_sonnet(monkeypatch, '```json\n{"chunks": [1, 3, 3, 99]}\n```')

    extra = select_extra_chunks(session, "q", [hits[0]])

    assert [c.text for c in extra] == ["Text C."]


def test_selection_is_capped(section_of_four, monkeypatch):
    session, hits = section_of_four
    monkeypatch.setattr(settings, "MAX_SELECTED", 1)
    fake_sonnet(monkeypatch, '{"chunks": [2, 3, 4]}')

    assert len(select_extra_chunks(session, "q", [hits[0]])) == 1


@pytest.mark.parametrize("reply", ["not json", '{"chunks": "all"}', '{"chunks": ["a"]}', '{"other": []}', RuntimeError("down")])
def test_a_failing_or_invalid_selection_adds_nothing(section_of_four, monkeypatch, reply):
    session, hits = section_of_four
    fake_sonnet(monkeypatch, reply)

    assert select_extra_chunks(session, "q", [hits[0]]) == []


def test_no_call_when_every_chunk_of_the_sections_is_kept(section_of_four, monkeypatch):
    session, hits = section_of_four
    calls = fake_sonnet(monkeypatch, '{"chunks": []}')

    assert select_extra_chunks(session, "q", [hits[4]]) == []  # the second section has only one chunk
    assert calls == []


def test_parse_selection_rejects_booleans():
    with pytest.raises(ValueError):
        parse_selection('{"chunks": [true]}')
