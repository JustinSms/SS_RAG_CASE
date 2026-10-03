"""Question files (YAML, one per PDF): load, check, and copy into the eval database."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Document, Section
from eval.db import Gold, Question

QUESTION_TYPES = ("single_fact", "multi_chunk", "cross_document", "follow_up", "unanswerable")
HISTORY_ROLES = ("user", "assistant")


@dataclass
class QuestionSpec:
    id: str
    document: str
    question: str
    type: str
    answerable: bool
    gold: list[tuple[str, str]] = field(default_factory=list)  # (document, heading path)
    history: list[dict] = field(default_factory=list)


def check(raw: dict) -> list[str]:
    """What is wrong with one question entry (empty if nothing)."""
    name = raw.get("id", "?")
    problems = []
    for key in ("id", "document", "question", "type", "answerable"):
        if key not in raw:
            problems.append(f"{name}: missing '{key}'")
    if raw.get("type") not in QUESTION_TYPES:
        problems.append(f"{name}: type must be one of {', '.join(QUESTION_TYPES)}")
    gold = raw.get("gold") or []
    if raw.get("answerable") and not gold:
        problems.append(f"{name}: an answerable question needs gold")
    if raw.get("answerable") is False and gold:
        problems.append(f"{name}: an unanswerable question must have no gold")
    if (raw.get("type") == "unanswerable") == bool(raw.get("answerable")):
        problems.append(f"{name}: type 'unanswerable' and answerable do not agree")
    if raw.get("type") == "follow_up" and not raw.get("history"):
        problems.append(f"{name}: a follow_up needs history")
    for entry in gold:
        if not entry.get("document") or not entry.get("heading"):
            problems.append(f"{name}: each gold entry needs document and heading")
    for turn in raw.get("history") or []:
        if turn.get("role") not in HISTORY_ROLES or not turn.get("content"):
            problems.append(f"{name}: each history turn needs a role (user or assistant) and content")
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
                        raw["id"], raw["document"], raw["question"], raw["type"], raw["answerable"],
                        [(g["document"], g["heading"]) for g in raw.get("gold") or []],
                        raw.get("history") or [],
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
    """Replace the questions in the database with the ones from the files. Results of earlier runs go with them."""
    problems = missing_headings(session, specs)
    if problems:
        raise ValueError("Gold headings not found:\n" + "\n".join(problems))
    session.execute(delete(Question))
    for s in specs:
        session.add(Question(id=s.id, document=s.document, question=s.question, type=s.type,
                             answerable=s.answerable, history=s.history))
    session.flush()  # questions first: gold rows point at them
    for s in specs:
        for document, heading in s.gold:
            session.add(Gold(question_id=s.id, document=document, heading=heading))
    session.commit()
