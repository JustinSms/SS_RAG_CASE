"""B1-B8 for one question. Rewrite and section selection are added in a later milestone."""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.llm.client import complete
from app.llm.prompts import answer_system
from app.retrieval.citations import Source, clean_citations, strip_citations
from app.retrieval.embedder import get_embedder
from app.retrieval.reranker import get_reranker
from app.retrieval.search import SCORES_LOGGED, Hit, search_chunks
from env.config import settings

log = logging.getLogger(__name__)

NOT_FOUND = "I could not find this in your documents."
MESSAGES_PER_TURN = 2  # one question and one answer


@dataclass
class Trace:
    """Chunk ids after each stage, for the evaluation."""

    candidates: list[uuid.UUID] = field(default_factory=list)  # B2: above the cutoff, best cosine first
    reranked: list[uuid.UUID] | None = None  # B3: best rerank score first; None if the reranker failed
    best_rerank_score: float | None = None
    top_n: list[uuid.UUID] = field(default_factory=list)  # B4: the chunks kept
    not_found: bool = False  # B4: the answer model is not called


@dataclass
class ChatResult:
    answer: str
    sources: dict[str, Source]
    trace: Trace = field(default_factory=Trace)


def rerank(question: str, hits: list[Hit]) -> tuple[list[Hit], float | None]:
    """B3: the hits best first, and the best score. Reranker failure keeps the cosine order (score None)."""
    try:
        scores = get_reranker().score(question, [h.text for h in hits])
    except Exception:
        log.exception("reranking failed; using the cosine order")
        return hits, None
    ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
    log.info("best rerank scores: %s", [round(score, 3) for _, score in ranked[:SCORES_LOGGED]])
    return [hit for hit, _ in ranked], ranked[0][1]


def select_context(session: Session, question: str) -> tuple[list[Hit], Trace]:
    """B1-B4 and B7: the chunks the answer is based on, in document order (empty: not found)."""
    trace = Trace()
    vector = get_embedder().embed([question])[0]  # B1
    hits = search_chunks(session, vector)  # B2
    trace.candidates = [h.chunk_id for h in hits]
    if not hits:
        trace.not_found = True
        return [], trace

    ranked, trace.best_rerank_score = rerank(question, hits)  # B3
    if trace.best_rerank_score is not None:
        trace.reranked = [h.chunk_id for h in ranked]
    top = ranked[: settings.TOP_N]  # B4
    trace.top_n = [h.chunk_id for h in top]
    if trace.best_rerank_score is not None and trace.best_rerank_score < settings.RERANK_MIN_SCORE:
        trace.not_found = True
        return [], trace

    return sorted(top, key=lambda h: (h.filename, h.document_id, h.position_in_document)), trace  # B7


def history_messages(history: list[dict]) -> list[dict]:
    """The last HISTORY_TURNS turns, starting with a question. Old [cXX] ids no longer apply."""
    recent = history[-settings.HISTORY_TURNS * MESSAGES_PER_TURN :]
    while recent and recent[0]["role"] != "user":
        recent = recent[1:]
    return [{"role": m["role"], "content": strip_citations(m["content"])} for m in recent]


def answer_question(session: Session, question: str, history: list[dict]) -> ChatResult:
    context, trace = select_context(session, question)
    if trace.not_found:  # do not call the answer model
        return ChatResult(NOT_FOUND, {}, trace)

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
    return ChatResult(clean_citations(answer, sources), sources, trace)
