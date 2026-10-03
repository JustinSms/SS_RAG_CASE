import pytest

from eval import metrics
from eval.metrics import Chunk, Gold, Record, Thresholds
from env.config import settings

DOC = "act.pdf"


def chunk(n, path, cosine=0.8, rerank=0.9, document=DOC, chars=400):
    return Chunk(f"c{n}", document, path, chars, cosine, rerank)


def record(gold_paths, candidates=(), final=(), answerable=True, refused=False, document=DOC, qid="q"):
    return Record(
        qid, document, "single_fact", answerable, [Gold(DOC, p) for p in gold_paths],
        list(candidates), list(final), refused, 1.0,
    )


T = Thresholds(cutoff=0.4, min_score=0.1, top_n=2)


def test_a_chunk_in_the_gold_section_or_a_subsection_overlaps():
    gold = Gold(DOC, "3 Rules > 3.2 Limits")
    assert metrics.overlaps(chunk(1, "3 Rules > 3.2 Limits"), gold)
    assert metrics.overlaps(chunk(2, "3 Rules > 3.2 Limits > 3.2.1 Caps"), gold)


def test_a_parent_section_a_sibling_or_another_document_does_not_overlap():
    gold = Gold(DOC, "3 Rules > 3.2 Limits")
    assert not metrics.overlaps(chunk(1, "3 Rules"), gold)
    assert not metrics.overlaps(chunk(2, "3 Rules > 3.3 Fees"), gold)
    assert not metrics.overlaps(chunk(3, "3 Rules > 3.2 Limits extra"), gold)  # same prefix, other heading
    assert not metrics.overlaps(chunk(4, "3 Rules > 3.2 Limits", document="other.pdf"), gold)


def test_answerable_scores_precision_recall_and_hit():
    r = record(["A", "B"])
    s = metrics.score(r, [chunk(1, "A"), chunk(2, "A > A.1"), chunk(3, "C"), chunk(4, "C")], refused=False)

    assert s.correct
    assert s.precision == 0.5  # 2 of 4 chunks are in a gold section
    assert s.recall == 0.5  # gold A is covered, gold B is not
    assert s.tokens == 4 * 400 / settings.CHARS_PER_TOKEN


def test_answerable_with_no_overlap_or_a_refusal_is_wrong():
    r = record(["A"])
    assert not metrics.score(r, [chunk(1, "B")], refused=False).correct
    refused = metrics.score(r, [], refused=True)
    assert not refused.correct and refused.precision == 0 and refused.recall == 0


def test_unanswerable_is_correct_only_when_the_system_refuses():
    r = record([], answerable=False)
    assert metrics.score(r, [], refused=True).correct
    assert not metrics.score(r, [chunk(1, "A")], refused=False).correct


def test_stage_one_keeps_what_is_above_the_cutoff():
    r = record(["A"], [chunk(1, "A", cosine=0.9), chunk(2, "B", cosine=0.3)])
    chunks, refused = metrics.context_after_cosine(r, T)
    assert [c.id for c in chunks] == ["c1"] and not refused

    _, refused = metrics.context_after_cosine(r, Thresholds(0.95, 0.1, 2))
    assert refused


def test_stage_two_reranks_cuts_to_top_n_and_refuses_on_a_low_score():
    candidates = [chunk(1, "B", 0.9, 0.2), chunk(2, "A", 0.8, 0.95), chunk(3, "C", 0.7, 0.5), chunk(4, "D", 0.6, 0.4)]
    r = record(["A"], candidates)

    chunks, refused = metrics.context_after_rerank(r, T)
    assert [c.id for c in chunks] == ["c2", "c3"] and not refused

    chunks, refused = metrics.context_after_rerank(r, Thresholds(0.4, 0.99, 2))
    assert chunks == [] and refused


def test_stage_two_without_rerank_scores_keeps_the_cosine_order():
    r = record(["A"], [chunk(1, "A", 0.9, None), chunk(2, "B", 0.8, None), chunk(3, "C", 0.7, None)])
    chunks, refused = metrics.context_after_rerank(r, T)
    assert [c.id for c in chunks] == ["c1", "c2"] and not refused


def test_the_final_stage_is_taken_as_it_was_run():
    r = record(["A"], final=[chunk(1, "A")], refused=False)
    assert metrics.context_for(r, "final", Thresholds(0.99, 0.99, 1)) == (r.final, False)


def test_summary_counts_refusals():
    scores = [
        metrics.score(record(["A"]), [chunk(1, "A")], False),  # hit
        metrics.score(record(["A"]), [], True),  # wrongly refused
        metrics.score(record([], answerable=False), [], True),  # right refusal
        metrics.score(record([], answerable=False), [chunk(1, "A")], False),  # missed refusal
    ]
    s = metrics.summarize(scores)

    assert (s.n, s.correct, s.answerable_n) == (4, 2, 2)
    assert s.precision == 0.5 and s.recall == 0.5
    assert s.refusal_precision == (1, 2)  # 2 refusals, 1 right
    assert s.refusal_recall == (1, 2)  # 2 unanswerable, 1 refused


def test_wilson_interval_matches_a_known_value():
    low, high = metrics.wilson(83, 120, z=1.96)
    assert (round(low, 3), round(high, 3)) == (0.604, 0.767)  # same as scipy's Wilson interval
    assert metrics.wilson(0, 0) == (0.0, 0.0)
    low, high = metrics.wilson(120, 120)
    assert high == 1.0 and low > 0.95


def test_rates_are_printed_with_counts():
    assert metrics.format_rate(90, 120).startswith("90/120 (")
    assert metrics.format_rate(0, 0) == "-"


def test_sign_test_matches_the_design_examples():
    assert metrics.sign_test(12, 3) == pytest.approx(0.035, abs=0.001)
    assert metrics.sign_test(8, 5) == pytest.approx(0.581, abs=0.001)
    assert metrics.sign_test(0, 0) == 1.0


def test_flips_count_questions_only_one_side_gets_right():
    a = {"q1": True, "q2": True, "q3": False, "q4": False}
    b = {"q1": True, "q2": False, "q3": True, "q4": True}
    assert metrics.flips(a, b)[:2] == (1, 2)


def test_tuning_picks_the_middle_of_the_equally_good_settings(monkeypatch):
    monkeypatch.setattr(settings, "EVAL_CUTOFF_GRID", [0.3, 0.4, 0.5])
    monkeypatch.setattr(settings, "EVAL_RERANK_GRID", [0.1, 0.5])
    monkeypatch.setattr(settings, "EVAL_TOP_N_GRID", [1])
    # Answerable: the right chunk has cosine 0.9 and rerank 0.9, so every setting finds it.
    # Unanswerable: the best chunk has rerank 0.3: only min_score 0.5 refuses it.
    records = [
        record(["A"], [chunk(1, "A", 0.9, 0.9)], qid=f"a{n}") for n in range(5)
    ] + [
        record([], [chunk(2, "B", 0.9, 0.3)], answerable=False, qid=f"u{n}") for n in range(5)
    ]

    t = metrics.best_thresholds(records)

    assert t.min_score == 0.5  # the only value that refuses
    assert t.cutoff == 0.4  # all cutoffs tie; the middle one


def test_leave_one_pdf_out_tunes_on_the_other_pdfs(monkeypatch):
    monkeypatch.setattr(settings, "EVAL_CUTOFF_GRID", [0.4])
    monkeypatch.setattr(settings, "EVAL_RERANK_GRID", [0.1, 0.5])
    monkeypatch.setattr(settings, "EVAL_TOP_N_GRID", [1])
    # Only the questions of pdf "x" need min_score 0.5. Held out, "x" is tuned without them.
    x = [record([], [chunk(1, "B", 0.9, 0.3)], answerable=False, document="x.pdf", qid=f"x{n}") for n in range(4)]
    y = [record(["A"], [chunk(2, "A", 0.9, 0.3)], document="y.pdf", qid=f"y{n}") for n in range(4)]

    folds = metrics.leave_one_pdf_out(x + y)

    assert set(folds) == {"x.pdf", "y.pdf"}
    assert folds["x.pdf"].min_score == 0.1  # trained on y: a high threshold would refuse its answers
    assert folds["y.pdf"].min_score == 0.5  # trained on x: a high threshold refuses the unanswerable
