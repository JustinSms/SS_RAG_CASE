import pytest
import yaml
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Document, Section
from eval import questions
from eval.db import EvalBase, Gold, Question


@pytest.fixture
def session():
    """SQLite has no schemas: the `eval` schema is dropped from the table names."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    engine = engine.execution_options(schema_translate_map={"eval": None})
    Base.metadata.create_all(engine)
    EvalBase.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        document = Document(filename="act.pdf", sha256="x", size_bytes=1, status="ready")
        session.add(document)
        session.flush()
        session.add(Section(document_id=document.id, heading="Scope", level=1, heading_path="1 Scope",
                            position=0, page_start=1, page_end=1))
        session.commit()
        yield session


def entry(**changes):
    base = {"id": "q1", "document": "act.pdf", "question": "What is in scope?", "type": "single_fact",
            "answerable": True, "gold": [{"document": "act.pdf", "heading": "1 Scope"}], "history": []}
    return {**base, **changes}


def write(folder, *entries):
    (folder / "act.yaml").write_text(yaml.safe_dump(list(entries)))


def test_valid_questions_are_loaded(tmp_path):
    write(tmp_path, entry(), entry(id="q2", type="unanswerable", answerable=False, gold=[]))

    specs = questions.load_questions(tmp_path)

    assert [s.id for s in specs] == ["q1", "q2"]
    assert specs[0].gold == [("act.pdf", "1 Scope")]


def test_every_problem_is_reported_at_once(tmp_path):
    write(
        tmp_path,
        entry(gold=[]),  # answerable without gold
        entry(id="q2", type="nonsense"),
        entry(id="q3", type="follow_up"),  # no history
        entry(id="q3", type="unanswerable", answerable=False, gold=[]),  # duplicate id
        entry(id="q5", answerable=False),  # unanswerable with gold, type disagrees
    )

    with pytest.raises(ValueError) as error:
        questions.load_questions(tmp_path)

    message = str(error.value)
    for expected in ("q1: an answerable question needs gold", "q2: type must be one of", "q3: a follow_up needs history",
                     "duplicate id q3", "q5: an unanswerable question must have no gold"):
        assert expected in message


def test_a_gold_heading_that_is_not_in_the_tree_is_rejected(tmp_path, session):
    write(tmp_path, entry(gold=[{"document": "act.pdf", "heading": "9 Missing"}]))
    specs = questions.load_questions(tmp_path)

    with pytest.raises(ValueError, match="q1: '9 Missing' is not a heading of act.pdf"):
        questions.sync_questions(session, specs)


def test_sync_replaces_the_questions_and_their_gold(tmp_path, session):
    write(tmp_path, entry())
    questions.sync_questions(session, questions.load_questions(tmp_path))
    write(tmp_path, entry(id="q9", question="Another?"))

    questions.sync_questions(session, questions.load_questions(tmp_path))

    assert session.scalars(select(Question.id)).all() == ["q9"]
    assert [g.question_id for g in session.scalars(select(Gold))] == ["q9"]
