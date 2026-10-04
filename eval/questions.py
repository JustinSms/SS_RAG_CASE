"""Question files (YAML, one per PDF): load, check, and copy into the eval database."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Document, Section
from eval.db import Gold, Question

REQUIRED = ("id", "document", "question", "answerable")
FIELDS = (*REQUIRED, "gold")


@dataclass
class QuestionSpec:
    id: str
    document: str
    question: str
    answerable: bool
    gold: list[tuple[str, str]] = field(default_factory=list)  # (document, heading path)


def check(raw: dict) -> list[str]:
    """What is wrong with one question entry (empty if nothing)."""
    name = raw.get("id", "?")
    problems = []
    for key in REQUIRED:
        if key not in raw:
            problems.append(f"{name}: missing '{key}'")
    for key in raw:
        if key not in FIELDS:  # a typo, or a field of the old format (type, history)
            problems.append(f"{name}: unknown field '{key}'")
    if "answerable" in raw and not isinstance(raw["answerable"], bool):
        problems.append(f"{name}: answerable must be true or false")
    gold = raw.get("gold") or []
    if raw.get("answerable") and not gold:
        problems.append(f"{name}: an answerable question needs gold")
    if raw.get("answerable") is False and gold:
        problems.append(f"{name}: an unanswerable question must have no gold")
    for entry in gold:
        if not entry.get("document") or not entry.get("heading"):
            problems.append(f"{name}: each gold entry needs document and heading")
    return problems


def load_questions(folder: Path) -> list[QuestionSpec]:
    """All questions in the YAML files of a folder. Raises ValueError listing every problem."""
    problems = []
    specs = []
    ids = []
    for path in sorted(folder.glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text()) or []:
            ids.append(raw.get("id"))
            found = check(raw)
            problems += [f"{path.name}: {p}" for p in found]
            if not found:
                specs.append(
                    QuestionSpec(
                        raw["id"], raw["document"], raw["question"], raw["answerable"],
                        [(g["document"], g["heading"]) for g in raw.get("gold") or []],
                    )
                )
    problems += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if problems:
        raise ValueError("Problems in the question files:\n" + "\n".join(problems))
    return specs


def missing_headings(session: Session, specs: list[QuestionSpec]) -> list[str]:
    """Gold headings that are not in the ingested section trees (a typo, or the parser saw the PDF differently)."""
    known = set(session.execute(select(Document.filename, Section.heading_path).join(Section)).all())
    return [
        f"{s.id}: '{heading}' is not a heading of {document}"
        for s in specs
        for document, heading in s.gold
        if (document, heading) not in known
    ]


def sync_questions(session: Session, specs: list[QuestionSpec]) -> None:
    """Make the database match the files. Results of earlier runs are kept (rerun them after editing a question)."""
    problems = missing_headings(session, specs)
    if problems:
        raise ValueError("Gold headings not found:\n" + "\n".join(problems))
    session.execute(delete(Question).where(Question.id.not_in([s.id for s in specs])))
    session.execute(delete(Gold))
    for s in specs:
        session.merge(Question(id=s.id, document=s.document, question=s.question, answerable=s.answerable))
    session.flush()  # questions first: gold rows point at them
    for s in specs:
        for document, heading in s.gold:
            session.add(Gold(question_id=s.id, document=document, heading=heading))
    session.commit()
