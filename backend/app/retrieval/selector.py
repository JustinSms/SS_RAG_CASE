"""B5-B6: Sonnet picks the extra chunks of the kept sections that the answer needs."""

import json
import logging

from sqlalchemy.orm import Session

from app.llm.client import complete, strip_json_fence
from app.llm.prompts import SELECT_SYSTEM, SELECT_USER
from app.retrieval.search import Hit, load_section_chunks
from env.config import settings

log = logging.getLogger(__name__)


def select_extra_chunks(session: Session, question: str, top: list[Hit]) -> list[Hit]:
    """The chunks, not in `top`, that the model wants as well. On any failure: none."""
    section_ids = list(dict.fromkeys(h.section_id for h in top))  # B5
    kept = {h.chunk_id for h in top}
    try:
        chunks = load_section_chunks(session, section_ids)
        if all(c.chunk_id in kept for c in chunks):  # nothing left to pick from
            return []
        numbered = dict(enumerate(chunks, start=1))
        prompt = SELECT_USER.format(question=question, sections=describe_sections(numbered, kept))
        reply = complete(
            settings.SELECT_MODEL, SELECT_SYSTEM, [{"role": "user", "content": prompt}], settings.SELECT_MAX_TOKENS
        )
        numbers = parse_selection(reply)
    except Exception:
        log.exception("section selection failed; using the top chunks only")
        return []

    picked = [numbered[n] for n in numbers if n in numbered and numbered[n].chunk_id not in kept]
    return picked[: settings.MAX_SELECTED]


def describe_sections(numbered: dict[int, Hit], kept: set) -> str:
    """One block per section: each chunk with its number, pages, summary and keywords."""
    blocks: dict = {}
    for number, chunk in numbered.items():
        if chunk.section_id not in blocks:
            blocks[chunk.section_id] = [f"Section: {chunk.heading_path} ({chunk.filename})"]
        pages = f"p. {chunk.page_start}" if chunk.page_start == chunk.page_end else f"p. {chunk.page_start}-{chunk.page_end}"
        status = "kept" if chunk.chunk_id in kept else "not kept"
        if chunk.summary:  # an unenriched chunk shows the start of its text instead
            body = f"Summary: {chunk.summary} Keywords: {', '.join(chunk.keywords or [])}"
        else:
            body = f"Text: {chunk.text[: settings.SELECT_FALLBACK_CHARS]}"
        blocks[chunk.section_id].append(f"[{number}] ({status}, {pages}) {body}")
    return "\n\n".join("\n".join(lines) for lines in blocks.values())


def parse_selection(reply: str) -> list[int]:
    """The chunk numbers from {"chunks": [3, 7]}, without duplicates. Anything else is an error."""
    numbers = json.loads(strip_json_fence(reply))["chunks"]
    if not isinstance(numbers, list) or not all(isinstance(n, int) and not isinstance(n, bool) for n in numbers):
        raise ValueError("chunks must be a list of numbers")
    return list(dict.fromkeys(numbers))
