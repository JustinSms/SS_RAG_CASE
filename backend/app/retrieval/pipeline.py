"""B1-B8 for one question. Rewrite, rerank and section selection are added in later milestones."""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.llm.client import complete
from app.llm.prompts import answer_system
from app.retrieval.citations import Source, clean_citations, strip_citations
from app.retrieval.embedder import get_embedder
from app.retrieval.search import Hit, search_chunks
from env.config import settings

log = logging.getLogger(__name__)

NOT_FOUND = "I could not find this in your documents."
MESSAGES_PER_TURN = 2  # one question and one answer


@dataclass
class ChatResult:
    answer: str
    sources: dict[str, Source]


def select_context(session: Session, question: str) -> list[Hit]:
    """B1, B2, B4 and B7: the chunks the answer is based on, in document order."""
    vector = get_embedder().embed([question])[0]  # B1
    hits = search_chunks(session, vector)  # B2
    top = hits[: settings.TOP_N]  # B4 (no reranker yet, so top N by cosine)
    return sorted(top, key=lambda h: (h.filename, h.document_id, h.position_in_document))  # B7


def history_messages(history: list[dict]) -> list[dict]:
    """The last HISTORY_TURNS turns, starting with a question. Old [cXX] ids no longer apply."""
    recent = history[-settings.HISTORY_TURNS * MESSAGES_PER_TURN :]
    while recent and recent[0]["role"] != "user":
        recent = recent[1:]
    return [{"role": m["role"], "content": strip_citations(m["content"])} for m in recent]


def answer_question(session: Session, question: str, history: list[dict]) -> ChatResult:
    context = select_context(session, question)
    if not context:  # nothing above the cutoff: do not call the answer model
        return ChatResult(NOT_FOUND, {})

    sources = {}
    blocks = []
    for number, hit in enumerate(context, start=1):
        label = f"c{number}"
        sources[label] = Source(
            label, str(hit.document_id), hit.filename, hit.page_start, hit.page_end, hit.heading_path
        )
        pages = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"p. {hit.page_start}-{hit.page_end}"
        blocks.append(f"[{label}] {hit.filename}, {pages}, {hit.heading_path}\n{hit.text}")

    messages = history_messages(history) + [{"role": "user", "content": question}]
    answer = complete(  # B8
        settings.ANSWER_MODEL,
        answer_system("\n\n".join(blocks)),
        messages,
        settings.ANSWER_MAX_TOKENS,
    )
    return ChatResult(clean_citations(answer, sources), sources)
