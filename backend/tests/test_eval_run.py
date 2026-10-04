import logging

import pytest
from sqlalchemy import select

from app.retrieval import pipeline
from env.config import settings
from eval import run
from eval.db import Question, Result


def stages(session, label, question_id):
    rows = session.scalars(select(Result).where(Result.run == label, Result.question_id == question_id)).all()
    return {r.stage: r for r in rows}


def test_each_question_stores_its_candidates_and_final_context(eval_session):
    run.run_all(eval_session, "t")

    rows = stages(eval_session, "t", "n-01")
    assert set(rows) == {"candidates", "final"}
    chunk = rows["final"].chunks[0]
    assert chunk["document"] == "notes.pdf" and chunk["chars"] > 0
    assert rows["candidates"].chunks[0]["cosine"] == 0.8
    assert rows["candidates"].chunks[0]["rerank"] == 0.9  # the fake reranker's score
    assert not rows["final"].refused


def test_the_questions_are_run_without_history(eval_session, monkeypatch):
    seen = []
    original = pipeline.select_context
    monkeypatch.setattr(pipeline, "select_context", lambda s, q, history: seen.append(history) or original(s, q, history))

    run.run_all(eval_session, "t")

    assert seen == [[], []]


def test_a_failed_optional_step_is_reported_as_a_fallback(eval_session, monkeypatch):
    def failing_selection(session, question, top):  # fails, logs and falls back, like the real selector
        if "landlord" in question:
            logging.getLogger("app.retrieval.selector").error("section selection failed")
        return []

    monkeypatch.setattr(pipeline, "select_extra_chunks", failing_selection)

    fallbacks = run.run_all(eval_session, "t")

    assert fallbacks == ["n-02"]
    assert stages(eval_session, "t", "n-02")["final"].fallback
    assert not stages(eval_session, "t", "n-01")["final"].fallback


def test_a_rerun_replaces_the_run_and_keeps_other_runs(eval_session):
    run.run_all(eval_session, "a")
    run.run_all(eval_session, "b")
    run.run_all(eval_session, "a")

    assert len(eval_session.scalars(select(Result).where(Result.run == "a")).all()) == 4  # 2 questions x 2 stages
    assert len(eval_session.scalars(select(Result).where(Result.run == "b")).all()) == 4


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


def test_each_question_prints_a_progress_line(eval_session, capsys):
    run.run_all(eval_session, "t")

    out = capsys.readouterr().out
    assert "Run 't': 2 questions (2 answerable, 0 unanswerable)." in out
    assert "[1/2] n-01  hit" in out
    assert "| elapsed " in out and "| left ~" in out
    assert "| hits 2/2 | refused 0/0" in out  # running totals after the second question


def test_a_fallback_is_flagged_in_the_progress_line(eval_session, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "select_extra_chunks", lambda session, question, top: (
        logging.getLogger("app.retrieval.selector").error("section selection failed") or []))

    run.run_all(eval_session, "t")

    assert "FALLBACK" in capsys.readouterr().out


def test_the_verdict_names_what_went_wrong():
    answerable, unanswerable = Question(answerable=True), Question(answerable=False)
    assert run.verdict(answerable, run.Outcome(True, False, 1.0, False)) == "hit"
    assert run.verdict(answerable, run.Outcome(False, True, 1.0, False)) == "miss (refused)"
    assert run.verdict(answerable, run.Outcome(False, False, 1.0, False)) == "miss"
    assert run.verdict(unanswerable, run.Outcome(True, True, 1.0, False)) == "refused"
    assert run.verdict(unanswerable, run.Outcome(False, False, 1.0, False)) == "not refused"


def test_only_the_full_run_needs_the_api_key(monkeypatch):
    monkeypatch.setattr(run, "check_api_key", lambda: "missing")
    run.require_api_key(scores_only=True)  # no model call in the scores-only run
    with pytest.raises(SystemExit):
        run.require_api_key(scores_only=False)
