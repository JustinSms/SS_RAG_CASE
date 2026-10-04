import json

import pytest

from env.config import settings
from eval import report, run
from eval.metrics import Chunk, Gold, Record, Thresholds

T = Thresholds(0.4, 0.1, 2)


def chunk(n, path, document="a.pdf", cosine=0.8, rerank=0.9):
    return Chunk(f"c{n}", document, path, 400, cosine, rerank)


def record(qid, document="a.pdf", answerable=True, gold=("1 Scope",), final=(), refused=False):
    chunks = list(final)
    return Record(qid, document, answerable, [Gold(document, g) for g in gold], chunks, chunks, refused, 1.5)


@pytest.fixture
def records():
    return [
        record("a-01", final=[chunk(1, "1 Scope")]),  # hit
        record("a-02", final=[chunk(2, "2 Other")]),  # miss
        record("a-03", answerable=False, gold=(), refused=True),  # right refusal
        record("b-01", document="b.pdf", final=[chunk(3, "1 Scope", "b.pdf")]),  # hit
    ]


@pytest.fixture
def folds():
    return {"a.pdf": T, "b.pdf": T}


def test_the_report_separates_answerable_and_unanswerable_questions(records, folds):
    text = report.render(records, records, folds, {"a.pdf": 2.0}, [])

    assert "## Main table" in text
    assert "| All | 2/3 (" in text  # hits on the 3 answerable questions, counts next to the percentage
    assert "| 1/1 (" in text  # 1 of 1 unanswerable refused
    assert "| a.pdf | 1/2 (" in text
    assert "2.0" in text  # chunks per section


def test_the_report_lists_every_failure_with_gold_and_retrieved(records, folds):
    text = report.render(records, records, folds, {}, [])

    assert "**a-02**: wanted a.pdf > 1 Scope. Got: a.pdf > 2 Other" in text
    assert "a-01" not in text.split("## Failures")[1].split("##")[0]


def test_the_report_says_that_answers_are_not_evaluated(records, folds):
    text = report.render(records, records, folds, {}, [])
    assert "generated answers are not evaluated yet" in text


def test_the_report_warns_about_fallbacks(records, folds):
    text = report.render(records, records, folds, {}, ["a-02"])
    assert "an optional step failed for 1 questions (a-02)" in text


def test_the_report_shows_refusal_precision(records, folds):
    text = report.render(records, records, folds, {}, [])
    assert "Refusal precision 1/1" in text


def test_the_report_has_no_precision_recall_or_stage_table(records, folds):
    text = report.render(records, records, folds, {}, [])
    assert "Recall" not in text and "| Precision" not in text and "1. Cosine" not in text


def test_records_are_loaded_from_a_stored_run(eval_session):
    run.run_all(eval_session, "t")

    records = report.load_records(eval_session, "t")

    assert [r.question_id for r in records] == ["n-01", "n-02"]
    assert records[0].gold[0].document == "notes.pdf"
    assert records[0].candidates[0].cosine == 0.8 and records[0].final[0].document == "notes.pdf"
    assert report.fallback_questions(eval_session, "t") == []
    assert report.chunks_per_section(eval_session)["notes.pdf"] >= 1


def test_an_incomplete_run_is_rejected(eval_session):
    with pytest.raises(SystemExit, match="missing"):
        report.load_records(eval_session, "never-run")


def test_a_stored_run_can_be_tuned_and_reported(eval_session, tmp_path, monkeypatch):
    monkeypatch.setattr(report, "FOLDS_FILE", tmp_path / "folds.json")
    monkeypatch.setattr(report, "RESULTS_FILE", tmp_path / "results.md")
    run.run_all(eval_session, "sweep", scores_only=True)
    run.run_all(eval_session, "final")

    report.tune(eval_session, "sweep")
    report.report(eval_session, "sweep", "final", tmp_path / "folds.json")

    folds = json.loads((tmp_path / "folds.json").read_text())
    assert set(folds["notes.pdf"]) == {"cutoff", "min_score", "top_n"}
    assert folds["notes.pdf"]["top_n"] in settings.EVAL_TOP_N_GRID
    assert "| All | " in (tmp_path / "results.md").read_text()


def test_compare_prints_the_flip_counts(eval_session, tmp_path, capsys):
    run.run_all(eval_session, "a")
    run.run_all(eval_session, "b")
    folds = tmp_path / "folds.json"
    folds.write_text(json.dumps({"notes.pdf": {"cutoff": 0.4, "min_score": 0.1, "top_n": 5}}))

    report.compare(eval_session, "a", "b", folds)

    assert "A only: 0, B only: 0, p = 1.000" in capsys.readouterr().out
