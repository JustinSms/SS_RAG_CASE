from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from env.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


def get_session():
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session


def create_tables() -> None:
    """Called at startup. The vector extension must exist before the vector column."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
