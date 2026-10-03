import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Chunk, Document, Section
from app.retrieval import pipeline
from app.retrieval.search import to_hit
from env.config import settings
from eval import ingest, run
from eval.db import EvalBase, Result
from tests.conftest import make_pdf


@pytest.fixture
def eval_session(session_factory, tmp_path, monkeypatch):
    """The test database with the eval tables added, a PDF ingested and a question file written."""
    engine = session_factory.kw["bind"].execution_options(schema_translate_map={"eval": None})
    EvalBase.metadata.create_all(engine)

    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "notes.pdf").write_bytes(make_pdf("The notice period is thirty days."))
    ingest.ingest_all(session_factory, pdfs, tmp_path / "trees")

    with session_factory() as session:
        heading = session.scalar(select(Section.heading_path))
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "notes.yaml").write_text(yaml.safe_dump([
        {"id": "n-01", "document": "notes.pdf", "question": "How long is the notice period?", "type": "single_fact",
         "answerable": True, "gold": [{"document": "notes.pdf", "heading": heading}]},
        {"id": "n-02", "document": "notes.pdf", "question": "And for the landlord?", "type": "follow_up",
         "answerable": True, "gold": [{"document": "notes.pdf", "heading": heading}],
         "history": [{"role": "user", "content": "How long is the notice period?"}]},
    ]))
    monkeypatch.setattr(run, "QUESTIONS_DIR", questions)

    def search(session, vector):  # pgvector's cosine search does not run on SQLite
        rows = session.execute(
            select(Chunk, Section.heading_path, Document.filename)
            .join(Section, Chunk.section_id == Section.id).join(Document, Chunk.document_id == Document.id)
        ).all()
        hits = [to_hit(c, path, name, 0.8) for c, path, name in rows]
        return [h for h in hits if h.similarity >= settings.SIMILARITY_CUTOFF]

    monkeypatch.setattr(pipeline, "search_chunks", search)
    with sessionmaker(engine)() as session:
        yield session


def stages(session, label, question_id):
    rows = session.scalars(select(Result).where(Result.run == label, Result.question_id == question_id)).all()
    return {r.stage: r for r in rows}


def test_each_question_stores_its_three_stages(eval_session):
    run.run_all(eval_session, "t")

    rows = stages(eval_session, "t", "n-01")
    assert set(rows) == {"cosine", "rerank", "final"}
    chunk = rows["final"].chunks[0]
    assert chunk["document"] == "notes.pdf" and chunk["chars"] > 0
    assert rows["cosine"].chunks[0]["cosine"] == 0.8
    assert rows["cosine"].chunks[0]["rerank"] == 0.9  # the fake reranker's score
    assert not rows["final"].refused


def test_a_failed_rewrite_is_reported_as_a_fallback(eval_session):
    fallbacks = run.run_all(eval_session, "t")  # the test setup makes every Anthropic call fail

    assert fallbacks == ["n-02"]  # only the follow-up needs the rewrite
    assert stages(eval_session, "t", "n-02")["final"].fallback
    assert not stages(eval_session, "t", "n-01")["final"].fallback


def test_a_rerun_replaces_the_run_and_keeps_other_runs(eval_session):
    run.run_all(eval_session, "a")
    run.run_all(eval_session, "b")
    run.run_all(eval_session, "a")

    assert len(eval_session.scalars(select(Result).where(Result.run == "a")).all()) == 6
    assert len(eval_session.scalars(select(Result).where(Result.run == "b")).all()) == 6


def test_the_run_uses_the_thresholds_it_is_given_and_restores_the_settings(eval_session):
    before = (settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N)
    folds = {"notes.pdf": {"cutoff": 0.95, "min_score": 0.1, "top_n": 1}}  # the fake chunks score 0.8: nothing passes

    run.run_all(eval_session, "t", folds=folds)

    assert stages(eval_session, "t", "n-01")["final"].refused
    assert (settings.SIMILARITY_CUTOFF, settings.RERANK_MIN_SCORE, settings.TOP_N) == before


def test_scores_only_uses_the_loosest_settings_and_skips_selection(eval_session, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "select_extra_chunks", lambda *a: calls.append(a) or [])
    seen = []
    original = run.thresholds_for
    monkeypatch.setattr(run, "thresholds_for", lambda *a: seen.append(original(*a)) or seen[-1])

    run.run_all(eval_session, "sweep", scores_only=True)

    assert seen[0].cutoff == min(settings.EVAL_CUTOFF_GRID) and seen[0].top_n == max(settings.EVAL_TOP_N_GRID)
    assert calls == []
