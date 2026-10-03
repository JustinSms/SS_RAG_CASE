from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.db.session import SessionLocal, create_tables
from app.health import router as health_router
from app.ingestion.queue import DocumentQueue, recover_interrupted
from app.llm.client import check_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.key_status = check_api_key()  # once at startup, result cached
    create_tables()
    recover_interrupted(SessionLocal)
    app.state.queue = DocumentQueue(SessionLocal)
    app.state.queue.start()
    yield
    app.state.queue.stop()


app = FastAPI(title="Document Chat", lifespan=lifespan)
app.include_router(health_router)
app.include_router(documents_router)
