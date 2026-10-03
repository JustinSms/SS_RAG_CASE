"""Metrics from stored runs, as eval/results.md. Nothing here calls a model.

    python report.py tune --sweep sweep           # leave-one-PDF-out thresholds -> folds.json
    python report.py report --sweep sweep --final final
    python report.py compare --a run1 --b run2    # which questions only one of two runs gets right
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, Section
from env.config import settings
from eval import metrics
from eval.db import Gold, Question, Result
from eval.metrics import Chunk as RunChunk
from eval.metrics import Record, Thresholds

EVAL_DIR = Path(__file__).parent
FOLDS_FILE = EVAL_DIR / "folds.json"
RESULTS_FILE = EVAL_DIR / "results.md"
STAGES = {"cosine": "1. Cosine", "rerank": "2. Rerank", "final": "3. Final context (headline)"}
SLOW_PERCENTILE = 0.95
PERCENT = 100


# --- loading --------------------------------------------------------------------------------------

def load_records(session: Session, run: str) -> list[Record]:
    """Every question of a run. Stops if the run is missing questions."""
    questions = session.scalars(select(Question).order_by(Question.id)).all()
    gold = defaultdict(list)
    for g in session.scalars(select(Gold)):
        gold[g.question_id].append(metrics.Gold(g.document, g.heading))
    stages = defaultdict(dict)
    for r in session.scalars(select(Result).where(Result.run == run)):
        stages[r.question_id][r.stage] = r
    missing = [q.id for q in questions if "final" not in stages[q.id]]
    if not stages or missing:
        raise SystemExit(f"Run '{run}' is missing {len(missing)} of {len(questions)} questions. Run it again.")

    def chunks(row: Result) -> list[RunChunk]:
        return [RunChunk(c["id"], c["document"], c["heading_path"], c["chars"], c["cosine"], c["rerank"]) for c in row.chunks]

    return [
        Record(q.id, q.document, q.type, q.answerable, gold[q.id], chunks(stages[q.id]["cosine"]),
               chunks(stages[q.id]["final"]), stages[q.id]["final"].refused, stages[q.id]["final"].latency_s)
        for q in questions
    ]


def fallback_questions(session: Session, run: str) -> list[str]:
    return sorted({r.question_id for r in session.scalars(select(Result).where(Result.run == run, Result.fallback))})


def chunks_per_section(session: Session) -> dict[str, float]:
    """Average chunks in a section that has chunks, per PDF. Large sections make a hit easier."""
    per_section = (
        select(Chunk.document_id, Chunk.section_id, func.count().label("n")).group_by(Chunk.document_id, Chunk.section_id).subquery()
    )
    rows = session.execute(
        select(Document.filename, func.avg(per_section.c.n)).join(per_section, per_section.c.document_id == Document.id)
        .group_by(Document.filename)
    ).all()
    return {name: float(average) for name, average in rows}


# --- tables ---------------------------------------------------------------------------------------

def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def scored(records: list[Record], stage: str, folds: dict[str, Thresholds]) -> list[metrics.Score]:
    return [metrics.score(r, *metrics.context_for(r, stage, folds[r.document])) for r in records]


def percent(value: float) -> str:
    return f"{value * PERCENT:.0f}%"


def pair(ratio: tuple[int, int]) -> str:
    return metrics.format_rate(*ratio)


def main_row(label: str, records: list[Record], folds, per_section: float | None = None) -> list:
    s = metrics.summarize(scored(records, "final", folds))
    return [label, metrics.format_rate(s.correct, s.n), percent(s.recall), percent(s.precision), f"{s.tokens:.0f}",
            "-" if per_section is None else f"{per_section:.1f}"]


def main_table(records, folds, per_section) -> str:
    rows = [main_row("All", records, folds)]
    for document in sorted({r.document for r in records}):
        rows.append(main_row(document, [r for r in records if r.document == document], folds, per_section.get(document)))
    return table(["PDF", "Accuracy", "Recall", "Precision", "Context tokens", "Chunks per section"], rows)


def type_table(records, folds) -> str:
    rows = []
    for kind in sorted({r.type for r in records}):
        s = metrics.summarize(scored([r for r in records if r.type == kind], "final", folds))
        rows.append([kind, metrics.format_rate(s.correct, s.n)])
    overall = metrics.summarize(scored(records, "final", folds))
    text = table(["Question type", "Accuracy"], rows)
    return text + (
        f"\n\nRefusal precision {pair(overall.refusal_precision)} (of all \"not found\" answers, how many were right); "
        f"refusal recall {pair(overall.refusal_recall)} (of the unanswerable questions, how many were refused)."
    )


def tuning_section(sweep: list[Record], folds: dict[str, Thresholds]) -> str:
    pooled = metrics.best_thresholds(sweep)
    cutoffs, min_scores = settings.EVAL_CUTOFF_GRID, settings.EVAL_RERANK_GRID
    grid = table(
        ["RERANK_MIN_SCORE \\ SIMILARITY_CUTOFF"] + [str(c) for c in cutoffs],
        [[m] + [metrics.format_rate(metrics.accuracy_at(sweep, "rerank", Thresholds(c, m, pooled.top_n)), len(sweep))
                for c in cutoffs] for m in min_scores],
    )
    top_rows = []
    for n in settings.EVAL_TOP_N_GRID:
        t = Thresholds(pooled.cutoff, pooled.min_score, n)
        s = metrics.summarize(scored_at(sweep, t))
        top_rows.append([n, metrics.format_rate(s.correct, s.n), percent(s.recall), percent(s.precision)])
    fold_rows = [[d, t.cutoff, t.min_score, t.top_n] for d, t in sorted(folds.items())]
    return "\n\n".join([
        f"Accuracy after the rerank stage (no section selection), all {len(sweep)} questions. "
        f"Settings that get within {settings.EVAL_TUNE_TOLERANCE * PERCENT:.0f}% of the questions of the best count as equally good; "
        "the pick is the middle of them, not the single best value.",
        f"Pooled pick over all questions (the default to put in `env/config.py`): "
        f"`SIMILARITY_CUTOFF` {pooled.cutoff}, `RERANK_MIN_SCORE` {pooled.min_score}, `TOP_N` {pooled.top_n}.",
        f"**Cutoff and minimum rerank score** (`TOP_N` {pooled.top_n}):\n\n{grid}",
        f"**TOP_N** (cutoff {pooled.cutoff}, minimum score {pooled.min_score}):\n\n"
        + table(["TOP_N", "Accuracy", "Recall", "Precision"], top_rows),
        "**Leave-one-PDF-out picks** (tuned on the other PDFs; the headline table uses these for the held-out PDF):\n\n"
        + table(["Held-out PDF", "SIMILARITY_CUTOFF", "RERANK_MIN_SCORE", "TOP_N"], fold_rows),
    ])


def scored_at(records: list[Record], t: Thresholds) -> list[metrics.Score]:
    return [metrics.score(r, *metrics.context_for(r, "rerank", t)) for r in records]


def diagnostic_table(records, folds) -> str:
    rows = []
    for stage, label in STAGES.items():
        s = metrics.summarize(scored(records, stage, folds))
        rows.append([label, metrics.format_rate(s.correct, s.n), percent(s.recall), percent(s.precision), f"{s.tokens:.0f}"])
    return table(["Stage", "Accuracy", "Recall", "Precision", "Context tokens"], rows)


def failures(records: list[Record], folds) -> str:
    blocks = []
    for r in records:
        chunks, refused = metrics.context_for(r, "final", folds[r.document])
        if metrics.score(r, chunks, refused).correct:
            continue
        got = "refused (\"not found\")" if refused else "; ".join(f"{c.document} > {c.heading_path}" for c in chunks) or "nothing"
        wanted = "refusal" if not r.answerable else "; ".join(f"{g.document} > {g.heading}" for g in r.gold)
        blocks.append(f"- **{r.question_id}** ({r.type}): wanted {wanted}. Got: {got}")
    return "\n".join(blocks) or "None."


def latency_line(records: list[Record]) -> str:
    latencies = sorted(r.latency_s for r in records)
    p95 = latencies[min(len(latencies) - 1, int(SLOW_PERCENTILE * len(latencies)))]
    return f"Retrieval latency per question (including the rewrite and selection calls): mean {sum(latencies) / len(latencies):.1f} s, p95 {p95:.1f} s."


def trust_section(n: int) -> str:
    low, high = metrics.wilson(n // 2, n)
    return (
        f"The {n} questions are a sample, so every score is an estimate: at n={n} a score of 50% has an interval of about "
        f"±{(high - low) / 2 * PERCENT:.0f} points, and the intervals above (Wilson, 95%) are wider still for one PDF or one question type. "
        "Questions from the same PDF resemble each other, so read the per-PDF and per-type rows as indications of where retrieval fails. "
        "**The generated answers are not evaluated yet** (correctness, completeness, faithfulness, citation validity); "
        "good source overlap is necessary for a good answer but not sufficient. Evaluating the answers is the next step."
    )


def render(final: list[Record], sweep: list[Record], folds: dict[str, Thresholds], per_section: dict[str, float],
           fallbacks: list[str]) -> str:
    parts = [
        "# Retrieval evaluation",
        f"{len(final)} questions on {len({r.document for r in final})} PDFs. Source overlap only: a retrieved chunk is a hit if it is in the gold "
        "section or one of its subsections. Thresholds are cross-validated leave-one-PDF-out. Details: `docs/design/evaluation-metrics.md`.",
        "## Main table: final context (the chunks the answer model would get)",
        main_table(final, folds, per_section),
        latency_line(final),
        "## By question type",
        type_table(final, folds),
        "## Tuning",
        tuning_section(sweep, folds),
        "## Which step helps (diagnostic)",
        diagnostic_table(final, folds),
        "## Failures",
        failures(final, folds),
        "## How much to trust the numbers",
        trust_section(len(final)),
    ]
    if fallbacks:
        parts.insert(2, f"**Warning:** an optional step failed for {len(fallbacks)} questions ({', '.join(fallbacks)}); their rows do not show the real pipeline.")
    return "\n\n".join(parts) + "\n"


# --- commands -------------------------------------------------------------------------------------

def tune(session: Session, sweep: str) -> None:
    folds = metrics.leave_one_pdf_out(load_records(session, sweep))
    FOLDS_FILE.write_text(json.dumps({d: vars(t) for d, t in folds.items()}, indent=2) + "\n")
    print(f"Wrote {FOLDS_FILE.name}: " + "; ".join(f"{d}: {t}" for d, t in folds.items()))


def report(session: Session, sweep: str, final: str, folds_file: Path) -> None:
    folds = {d: Thresholds(**t) for d, t in json.loads(folds_file.read_text()).items()}
    text = render(load_records(session, final), load_records(session, sweep), folds, chunks_per_section(session),
                  fallback_questions(session, final))
    RESULTS_FILE.write_text(text)
    print(f"Wrote {RESULTS_FILE.name}")


def compare(session: Session, a: str, b: str, folds_file: Path) -> None:
    folds = {d: Thresholds(**t) for d, t in json.loads(folds_file.read_text()).items()}

    def correct(run):
        records = load_records(session, run)
        return {r.question_id: s.correct for r, s in zip(records, scored(records, "final", folds))}

    only_a, only_b, p = metrics.flips(correct(a), correct(b))
    print(f"A only: {only_a}, B only: {only_b}, p = {p:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["tune", "report", "compare"])
    parser.add_argument("--sweep", default="sweep", help="run made with --scores-only")
    parser.add_argument("--final", default="final", help="run made with --folds")
    parser.add_argument("--a")
    parser.add_argument("--b")
    parser.add_argument("--folds", type=Path, default=FOLDS_FILE)
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from eval.db import ensure_database

    ensure_database()
    with SessionLocal() as session:
        if args.command == "tune":
            tune(session, args.sweep)
        elif args.command == "report":
            report(session, args.sweep, args.final, args.folds)
        else:
            compare(session, args.a, args.b, args.folds)


if __name__ == "__main__":
    main()
