from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from env.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)
