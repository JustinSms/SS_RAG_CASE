"""Retrieval metrics on recorded runs: overlap between retrieved and gold sections.

Pure functions, no database and no models. See docs/design/evaluation-metrics.md.
"""

from dataclasses import dataclass
from itertools import product
from math import comb, sqrt
from statistics import mean

from env.config import settings

PATH_SEPARATOR = " > "  # between the headings of a heading path, as stored in sections.heading_path
PERCENT = 100


@dataclass(frozen=True)
class Gold:
    document: str
    heading: str  # a full heading path from the parser's section tree


@dataclass
class Chunk:
    id: str
    document: str
    heading_path: str
    chars: int
    cosine: float = 0.0  # 0 for chunks that were added by section selection
    rerank: float | None = None


@dataclass
class Record:
    """One question as it was run: the gold, and the chunks after each stage."""

    question_id: str
    document: str  # the PDF the question belongs to (the fold for the tuning)
    type: str
    answerable: bool
    gold: list[Gold]
    candidates: list[Chunk]  # B2, best cosine first, with cosine and rerank scores
    final: list[Chunk]  # B7 as it was run
    refused: bool  # as it was run
    latency_s: float


@dataclass(frozen=True)
class Thresholds:
    cutoff: float
    min_score: float
    top_n: int


@dataclass
class Score:
    correct: bool
    refused: bool
    answerable: bool
    precision: float
    recall: float
    tokens: float


@dataclass
class Summary:
    n: int
    correct: int
    answerable_n: int
    precision: float  # mean over answerable questions
    recall: float
    tokens: float  # mean over all questions that were answered
    refusal_precision: tuple[int, int]  # (correct refusals, all refusals)
    refusal_recall: tuple[int, int]  # (correct refusals, unanswerable questions)


def overlaps(chunk: Chunk, gold: Gold) -> bool:
    """The chunk is in the gold section or in one of its subsections, in the same document."""
    if chunk.document != gold.document:
        return False
    return chunk.heading_path == gold.heading or chunk.heading_path.startswith(gold.heading + PATH_SEPARATOR)


def context_after_cosine(record: Record, t: Thresholds) -> tuple[list[Chunk], bool]:
    """Stage 1: every candidate above the cutoff. Refused when there is none."""
    kept = [c for c in record.candidates if c.cosine >= t.cutoff]
    return kept, not kept


def context_after_rerank(record: Record, t: Thresholds) -> tuple[list[Chunk], bool]:
    """Stage 2: the top N of the candidates above the cutoff. Refused when none, or the best score is too low."""
    kept, refused = context_after_cosine(record, t)
    if refused:
        return [], True
    if all(c.rerank is not None for c in kept):
        kept = sorted(kept, key=lambda c: c.rerank, reverse=True)
        if kept[0].rerank < t.min_score:
            return [], True
    return kept[: t.top_n], False


def context_for(record: Record, stage: str, t: Thresholds) -> tuple[list[Chunk], bool]:
    """The chunks and the refusal at a stage. The final context cannot be recomputed (it needs the selection call)."""
    if stage == "cosine":
        return context_after_cosine(record, t)
    if stage == "rerank":
        return context_after_rerank(record, t)
    return record.final, record.refused


def score(record: Record, chunks: list[Chunk], refused: bool) -> Score:
    """Accuracy, precision and recall of one question."""
    tokens = sum(c.chars for c in chunks) / settings.CHARS_PER_TOKEN
    if not record.answerable:
        return Score(refused, refused, False, 0.0, 0.0, tokens)
    relevant = [c for c in chunks if any(overlaps(c, g) for g in record.gold)]
    covered = [g for g in record.gold if any(overlaps(c, g) for c in chunks)]
    precision = len(relevant) / len(chunks) if chunks else 0.0
    return Score(bool(relevant), refused, True, precision, len(covered) / len(record.gold), tokens)


def summarize(scores: list[Score]) -> Summary:
    answerable = [s for s in scores if s.answerable]
    answered = [s for s in scores if not s.refused]
    refusals = [s for s in scores if s.refused]
    return Summary(
        n=len(scores),
        correct=sum(s.correct for s in scores),
        answerable_n=len(answerable),
        precision=mean(s.precision for s in answerable) if answerable else 0.0,
        recall=mean(s.recall for s in answerable) if answerable else 0.0,
        tokens=mean(s.tokens for s in answered) if answered else 0.0,
        refusal_precision=(sum(not s.answerable for s in refusals), len(refusals)),
        refusal_recall=(sum(not s.answerable for s in refusals), len(scores) - len(answerable)),
    )


def wilson(k: int, n: int, z: float | None = None) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    z = settings.EVAL_CONFIDENCE_Z if z is None else z
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def format_rate(k: int, n: int) -> str:
    """'83/120 (75-89%)'"""
    if n == 0:
        return "-"
    low, high = wilson(k, n)
    return f"{k}/{n} ({low * PERCENT:.0f}-{high * PERCENT:.0f}%)"


def sign_test(only_a: int, only_b: int) -> float:
    """Two-sided exact sign test: how likely a split this uneven is when both are equally good."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2**n
    return min(1.0, 2 * tail)


def flips(correct_a: dict[str, bool], correct_b: dict[str, bool]) -> tuple[int, int, float]:
    """Questions only A gets right, only B gets right, and the sign test p-value."""
    shared = correct_a.keys() & correct_b.keys()
    only_a = sum(correct_a[q] and not correct_b[q] for q in shared)
    only_b = sum(correct_b[q] and not correct_a[q] for q in shared)
    return only_a, only_b, sign_test(only_a, only_b)


def grid() -> list[Thresholds]:
    return [
        Thresholds(cutoff, min_score, top_n)
        for cutoff, min_score, top_n in product(
            settings.EVAL_CUTOFF_GRID, settings.EVAL_RERANK_GRID, settings.EVAL_TOP_N_GRID
        )
    ]


def accuracy_at(records: list[Record], stage: str, t: Thresholds) -> int:
    """Number of correct questions at a stage under thresholds t."""
    return sum(score(r, *context_for(r, stage, t)).correct for r in records)


def middle(values: list, allowed: list):
    """The middle of the values that are in the grid, as a grid value (lower middle for an even count)."""
    chosen = sorted(set(values))
    return chosen[(len(chosen) - 1) // 2] if chosen else allowed[0]


def best_thresholds(records: list[Record]) -> Thresholds:
    """The middle of the settings whose stage-2 accuracy is within EVAL_TUNE_TOLERANCE of the best."""
    results = [(t, accuracy_at(records, "rerank", t)) for t in grid()]
    best = max(correct for _, correct in results)
    good = [t for t, correct in results if correct >= best - settings.EVAL_TUNE_TOLERANCE * len(records)]
    return Thresholds(
        middle([t.cutoff for t in good], settings.EVAL_CUTOFF_GRID),
        middle([t.min_score for t in good], settings.EVAL_RERANK_GRID),
        middle([t.top_n for t in good], settings.EVAL_TOP_N_GRID),
    )


def leave_one_pdf_out(records: list[Record]) -> dict[str, Thresholds]:
    """For each PDF: the thresholds tuned on all the other PDFs' questions."""
    documents = sorted({r.document for r in records})
    return {d: best_thresholds([r for r in records if r.document != d]) for d in documents}
