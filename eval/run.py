"""Run the retrieval (B0-B7) for every question and store the trace. The answer model is never called.

    python run.py --label sweep --scores-only      # loosest settings, no selection call: scores for the tuning
    python run.py --label final --folds folds.json # each PDF's questions with the thresholds tuned on the other PDFs
    python run.py --label default                  # the settings in env/config.py

A rerun with the same label replaces that run.
"""

import argparse
import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, Section
from app.llm.client import check_api_key
from app.retrieval import pipeline
from app.retrieval.reranker import get_reranker
from app.retrieval.search import Hit
from env.config import settings
from eval.db import Question, Result, ensure_database
from eval.metrics import Thresholds
from eval.questions import load_questions, sync_questions

QUESTIONS_DIR = Path(__file__).parent / "questions"
RETRIEVAL_LOGGER = "app.retrieval"  # the optional steps log an error here when they fall back


class FallbackCounter(logging.Handler):
    """Counts the errors the retrieval steps log when they fall back (rewrite, rerank, selection failed)."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.count = 0

    def emit(self, record):
        self.count += 1


@contextmanager
def thresholds_set(t: Thresholds):
    """The retrieval reads its thresholds from `settings`; set them for one question."""
    old = (settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N)
    settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N = t.cutoff, t.min_score, t.top_n
    try:
        yield
    finally:
        settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N = old


def describe(session: Session, ids: list, cosine: dict, rerank: dict) -> list[dict]:
    """The chunks as they are stored for the report: where they are and how they scored."""
    rows = session.execute(
        select(Chunk.id, Chunk.text, Section.heading_path, Chunk.document_id).join(Section, Chunk.section_id == Section.id)
        .where(Chunk.id.in_(ids))
    ).all()
    names = dict(session.execute(select(Document.id, Document.filename)).all())
    by_id = {row.id: row for row in rows}
    return [
        {
            "id": str(i),
            "document": names[by_id[i].document_id],
            "heading_path": by_id[i].heading_path,
            "chars": len(by_id[i].text),
            "cosine": cosine.get(i, 0.0),
            "rerank": rerank.get(i),
        }
        for i in ids
    ]


def run_question(session: Session, question: Question, run: str, t: Thresholds, counter: FallbackCounter) -> None:
    """Retrieve for one question and store the three stages."""
    before = counter.count
    started = time.perf_counter()
    with thresholds_set(t):
        context, trace = pipeline.select_context(session, question.question, question.history)
    latency = time.perf_counter() - started

    cosine = dict(zip(trace.candidates, trace.cosine_scores))
    rerank = dict(zip(trace.reranked or [], trace.rerank_scores or []))
    stages = {
        "cosine": trace.candidates,
        "rerank": trace.top_n if not trace.not_found else [],
        "final": [h.chunk_id for h in context],
    }
    # A follow-up that came back unchanged was not rewritten: the rewrite fell back.
    fallback = counter.count > before or (bool(question.history) and trace.search_question == question.question)
    for stage, ids in stages.items():
        session.add(Result(run=run, question_id=question.id, stage=stage, chunks=describe(session, ids, cosine, rerank),
                           refused=trace.not_found, latency_s=latency, fallback=fallback))
    session.commit()


def thresholds_for(question: Question, folds: dict | None, scores_only: bool) -> Thresholds:
    if scores_only:  # the loosest settings of the grid: every tuned setting is a subset of these candidates
        return Thresholds(min(settings.EVAL_CUTOFF_GRID), 0.0, max(settings.EVAL_TOP_N_GRID))
    if folds is None:
        return Thresholds(settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N)
    if question.document not in folds:
        raise SystemExit(f"{question.document} is not in the folds file.")
    return Thresholds(**folds[question.document])


def run_all(session: Session, label: str, folds: dict | None = None, scores_only: bool = False) -> list[str]:
    """Every question under one run label. Returns the ids of the questions that hit a fallback."""
    sync_questions(session, load_questions(QUESTIONS_DIR))
    questions = session.scalars(select(Question).order_by(Question.id)).all()
    if not questions:
        raise SystemExit(f"No questions found in {QUESTIONS_DIR}.")
    session.execute(delete(Result).where(Result.run == label))
    session.commit()

    counter = FallbackCounter()
    logging.getLogger(RETRIEVAL_LOGGER).addHandler(counter)
    original = pipeline.select_extra_chunks
    if scores_only:
        pipeline.select_extra_chunks = lambda session, question, top: []
    try:
        for number, question in enumerate(questions, start=1):
            print(f"[{number}/{len(questions)}] {question.id}", flush=True)
            run_question(session, question, label, thresholds_for(question, folds, scores_only), counter)
    finally:
        pipeline.select_extra_chunks = original
        logging.getLogger(RETRIEVAL_LOGGER).removeHandler(counter)

    return sorted({r.question_id for r in session.scalars(select(Result).where(Result.run == label, Result.fallback))})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, help="name of the run")
    parser.add_argument("--folds", type=Path, help="JSON file written by `report.py tune`")
    parser.add_argument("--scores-only", action="store_true", help="loosest settings and no selection call, for the tuning")
    args = parser.parse_args()

    from app.db.session import SessionLocal

    ensure_database()
    if check_api_key() != "ok":
        raise SystemExit("ANTHROPIC_API_KEY is missing or invalid: the rewrite and selection steps need it.")
    get_reranker()  # unlike in the app, a reranker that cannot load stops the run: the numbers would be wrong
    with SessionLocal() as session:
        folds = json.loads(args.folds.read_text()) if args.folds else None
        fallbacks = run_all(session, args.label, folds, args.scores_only)
    if fallbacks:
        print(f"WARNING: an optional step failed for {len(fallbacks)} questions: {', '.join(fallbacks)}")
        print("Their numbers do not show the real pipeline. Check the log above and rerun.")
        raise SystemExit(1)
    print(f"Run '{args.label}' stored.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
