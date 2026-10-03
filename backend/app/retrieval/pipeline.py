"""B0-B8 for one question."""

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.llm.client import complete, stream
from app.llm.prompts import answer_system
from app.retrieval.citations import Source, clean_citations, strip_citations
from app.retrieval.embedder import get_embedder
from app.retrieval.reranker import get_reranker
from app.retrieval.rewriter import rewrite_question
from app.retrieval.search import SCORES_LOGGED, Hit, search_chunks
from app.retrieval.selector import select_extra_chunks
from env.config import settings

log = logging.getLogger(__name__)

NOT_FOUND = "I could not find this in your documents."
MESSAGES_PER_TURN = 2  # one question and one answer


@dataclass
class Trace:
    """The question and chunk ids after each stage, for the evaluation."""

    search_question: str = ""  # B0: the standalone question used for retrieval
    candidates: list[uuid.UUID] = field(default_factory=list)  # B2: above the cutoff, best cosine first
    cosine_scores: list[float] = field(default_factory=list)  # B2: one per candidate
    reranked: list[uuid.UUID] | None = None  # B3: best rerank score first; None if the reranker failed
    rerank_scores: list[float] | None = None  # B3: one per reranked chunk
    best_rerank_score: float | None = None
    top_n: list[uuid.UUID] = field(default_factory=list)  # B4: the chunks kept
    not_found: bool = False  # B4: the answer model is not called
    selected: list[uuid.UUID] = field(default_factory=list)  # B6: extra chunks, beyond the top N


@dataclass
class ChatResult:
    answer: str
    sources: dict[str, Source]
    trace: Trace = field(default_factory=Trace)


def history_messages(history: list[dict]) -> list[dict]:
    """The last HISTORY_TURNS turns, starting with a question. Old [cXX] ids no longer apply."""
    recent = history[-settings.HISTORY_TURNS * MESSAGES_PER_TURN :]
    while recent and recent[0]["role"] != "user":
        recent = recent[1:]
    return [{"role": m["role"], "content": strip_citations(m["content"])} for m in recent]


def rerank(question: str, hits: list[Hit]) -> tuple[list[Hit], list[float] | None]:
    """B3: the hits best first, and their scores. Reranker failure keeps the cosine order (scores None)."""
    try:
        scores = get_reranker().score(question, [h.text for h in hits])
    except Exception:
        log.exception("reranking failed; using the cosine order")
        return hits, None
    ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
    log.info("best rerank scores: %s", [round(score, 3) for _, score in ranked[:SCORES_LOGGED]])
    return [hit for hit, _ in ranked], [score for _, score in ranked]


def combine(top: list[Hit], selected: list[Hit]) -> list[Hit]:
    """B7: the top N and the selected chunks, each chunk once, in document order."""
    unique = {h.chunk_id: h for h in [*top, *selected]}
    return sorted(unique.values(), key=lambda h: (h.filename, h.document_id, h.position_in_document))


def select_context(session: Session, question: str, history: list[dict]) -> tuple[list[Hit], Trace]:
    """B0-B7: the chunks the answer is based on, in document order (empty: not found)."""
    trace = Trace()
    trace.search_question = rewrite_question(question, history_messages(history))  # B0
    vector = get_embedder().embed([trace.search_question])[0]  # B1
    hits = search_chunks(session, vector)  # B2
    trace.candidates = [h.chunk_id for h in hits]
    trace.cosine_scores = [h.similarity for h in hits]
    if not hits:
        trace.not_found = True
        return [], trace

    ranked, trace.rerank_scores = rerank(trace.search_question, hits)  # B3
    if trace.rerank_scores is not None:
        trace.reranked = [h.chunk_id for h in ranked]
        trace.best_rerank_score = trace.rerank_scores[0]
    top = ranked[: settings.TOP_N]  # B4
    trace.top_n = [h.chunk_id for h in top]
    if trace.best_rerank_score is not None and trace.best_rerank_score < settings.RERANK_MIN_SCORE:
        trace.not_found = True
        return [], trace

    selected = select_extra_chunks(session, trace.search_question, top)  # B5-B6
    trace.selected = [h.chunk_id for h in selected]
    return combine(top, selected), trace  # B7


def build_prompt(context: list[Hit], question: str, history: list[dict]) -> tuple[dict[str, Source], str, list[dict]]:
    """B8: the source labels, the system prompt with the labelled chunks, and the messages."""
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
    return sources, answer_system("\n\n".join(blocks)), messages


def answer_question(session: Session, question: str, history: list[dict]) -> ChatResult:
    context, trace = select_context(session, question, history)
    if trace.not_found:  # do not call the answer model
        return ChatResult(NOT_FOUND, {}, trace)

    sources, system, messages = build_prompt(context, question, history)
    answer = complete(settings.ANSWER_MODEL, system, messages, settings.ANSWER_MAX_TOKENS)  # B8
    return ChatResult(clean_citations(answer, sources), sources, trace)


def stream_answer(session: Session, question: str, history: list[dict]) -> tuple[dict[str, Source], Iterator[str]]:
    """B0-B8 with a streamed answer: the retrieval runs now, the answer text arrives from the iterator.

    Ids that are not in the sources are not removed here (the text is not complete yet); the browser
    only shows tags for known ids.
    """
    context, trace = select_context(session, question, history)
    if trace.not_found:
        return {}, iter([NOT_FOUND])

    sources, system, messages = build_prompt(context, question, history)
    return sources, stream(settings.ANSWER_MODEL, system, messages, settings.ANSWER_MAX_TOKENS)
