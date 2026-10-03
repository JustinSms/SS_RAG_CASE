from app.ingestion.chunker import chunk_section
from app.ingestion.sections import Paragraph
from app.ingestion.tokens import count_tokens
from env.config import settings


def words(n, prefix="w"):
    return " ".join(f"{prefix}{i:03d}" for i in range(n))  # 5 characters + space each


def small_limits(monkeypatch, size=50, overlap=10):
    monkeypatch.setattr(settings, "MAX_CHUNK_SIZE", size)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP_TOKENS", overlap)


def test_a_short_section_is_one_chunk(monkeypatch):
    small_limits(monkeypatch)
    chunks = chunk_section([Paragraph("One.", 1), Paragraph("Two.", 2)])

    assert len(chunks) == 1
    assert chunks[0].text == "One.\n\nTwo."
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)


def test_chunks_never_exceed_the_maximum(monkeypatch):
    small_limits(monkeypatch)
    paragraphs = [Paragraph(words(8, f"p{i}"), 1) for i in range(12)]
    paragraphs.append(Paragraph(words(100, "long"), 1))  # one paragraph far over the limit

    chunks = chunk_section(paragraphs)

    assert len(chunks) > 3
    assert all(count_tokens(c.text) <= settings.MAX_CHUNK_SIZE for c in chunks)


def test_the_next_chunk_starts_with_the_end_of_the_previous_one(monkeypatch):
    small_limits(monkeypatch)
    paragraphs = [Paragraph(words(8, f"p{i}"), 1) for i in range(6)]

    chunks = chunk_section(paragraphs)

    overlap = chunks[1].text.split("\n\n")[0]
    assert chunks[0].text.endswith(overlap)
    assert 0 < count_tokens(overlap) <= settings.CHUNK_OVERLAP_TOKENS


def test_no_text_is_lost(monkeypatch):
    small_limits(monkeypatch)
    paragraphs = [Paragraph(words(8, f"p{i}"), 1) for i in range(6)]

    joined = " ".join(c.text for c in chunk_section(paragraphs))

    assert all(f"p{i}{j:03d}" in joined for i in range(6) for j in range(8))


def test_page_range_covers_a_chunk_that_spans_a_page_break(monkeypatch):
    small_limits(monkeypatch)
    paragraphs = [Paragraph(words(32, "a"), 3), Paragraph(words(10, "b"), 4)]  # 40 + 13 tokens

    chunks = chunk_section(paragraphs)

    assert [(c.page_start, c.page_end) for c in chunks] == [(3, 3), (3, 4)]  # overlap comes from page 3


def test_an_empty_section_has_no_chunks():
    assert chunk_section([]) == []
