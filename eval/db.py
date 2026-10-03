"""The evaluation database and its tables.

`docchat_eval` is created from code on start. It holds the normal app tables (the eval PDFs go
through the real ingestion) plus three tables in the `eval` schema. It is a different database
from the app's, so the chat never searches the eval PDFs.
"""

from sqlalchemy import JSON, ForeignKey, MetaData, Text, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.session import create_tables
from env.config import settings

SCHEMA = "eval"
ADMIN_DATABASE = "postgres"  # always exists; used to create the eval database


class EvalBase(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class Question(EvalBase):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(primary_key=True)
    document: Mapped[str]  # the PDF the question belongs to
    question: Mapped[str] = mapped_column(Text)
    type: Mapped[str]
    answerable: Mapped[bool]
    history: Mapped[list] = mapped_column(JSON, default=list)


class Gold(EvalBase):
    """Document name and heading path as text, no foreign key to `sections`: re-ingestion does not break it."""

    __tablename__ = "gold"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"))
    document: Mapped[str]
    heading: Mapped[str] = mapped_column(Text)


class Result(EvalBase):
    """The chunks of one question after one stage of one run."""

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run: Mapped[str]
    question_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.questions.id", ondelete="CASCADE"))
    stage: Mapped[str]  # cosine | rerank | final
    chunks: Mapped[list] = mapped_column(JSON)  # id, document, heading_path, chars, cosine, rerank
    refused: Mapped[bool]
    latency_s: Mapped[float]
    fallback: Mapped[bool] = mapped_column(default=False)  # an optional step failed: not the real pipeline


def ensure_database() -> None:
    """CREATE DATABASE if missing, then the tables. Refuses to touch any database but the eval one."""
    url = make_url(settings.DATABASE_URL)
    if url.database != settings.EVAL_DATABASE:
        raise SystemExit(
            f"DATABASE_URL points at '{url.database}', not '{settings.EVAL_DATABASE}'. "
            "Run the evaluation with: docker compose --profile eval run --rm eval ..."
        )
    admin = create_engine(url.set(database=ADMIN_DATABASE), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    create_tables()  # the app tables and the vector extension
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    EvalBase.metadata.create_all(engine)
    engine.dispose()
