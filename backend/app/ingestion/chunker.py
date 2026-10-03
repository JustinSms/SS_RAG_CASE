from dataclasses import dataclass

from app.ingestion.sections import Paragraph
from app.ingestion.tokens import count_tokens
from env.config import settings

SEPARATOR = "\n\n"


@dataclass
class ChunkDraft:
    text: str
    page_start: int
    page_end: int


def chunk_section(paragraphs: list[Paragraph]) -> list[ChunkDraft]:
    """A5: pack paragraphs into chunks of at most MAX_CHUNK_SIZE tokens.

    Each chunk after the first starts with the tail of the previous one
    (CHUNK_OVERLAP_TOKENS). Only the paragraphs of one section come in,
    so a chunk never crosses a section.
    """
    room = settings.MAX_CHUNK_SIZE - settings.CHUNK_OVERLAP_TOKENS  # new text per chunk
    pieces = [piece for p in paragraphs for piece in split_to_fit(p, room)]

    chunks: list[ChunkDraft] = []
    texts: list[str] = []  # the open chunk, overlap included
    pages: list[int] = []
    new_text = False  # does the open chunk hold more than the overlap?

    for piece in pieces:
        if texts and count_tokens(SEPARATOR.join(texts + [piece.text])) > settings.MAX_CHUNK_SIZE:
            chunks.append(ChunkDraft(SEPARATOR.join(texts), min(pages), max(pages)))
            overlap = Paragraph(tail(texts[-1], settings.CHUNK_OVERLAP_TOKENS), pages[-1])
            texts, pages, new_text = [overlap.text], [overlap.page], False
        texts.append(piece.text)
        pages.append(piece.page)
        new_text = True

    if new_text:
        chunks.append(ChunkDraft(SEPARATOR.join(texts), min(pages), max(pages)))
    return chunks


def split_to_fit(paragraph: Paragraph, max_tokens: int) -> list[Paragraph]:
    """A paragraph longer than max_tokens is cut at word boundaries."""
    if count_tokens(paragraph.text) <= max_tokens:
        return [paragraph]
    pieces: list[Paragraph] = []
    words: list[str] = []
    for word in paragraph.text.split():
        if words and count_tokens(" ".join(words + [word])) > max_tokens:
            pieces.append(Paragraph(" ".join(words), paragraph.page))
            words = []
        words.append(word)
    pieces.append(Paragraph(" ".join(words), paragraph.page))
    return pieces


def tail(text: str, max_tokens: int) -> str:
    """The last words of text that fit in max_tokens."""
    words = text.split()
    taken: list[str] = []
    for word in reversed(words):
        if count_tokens(" ".join([word] + taken)) > max_tokens:
            break
        taken.insert(0, word)
    return " ".join(taken)
