from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.health import router as health_router
from app.llm.client import check_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.key_status = check_api_key()  # once at startup, result cached
    yield


app = FastAPI(title="Document Chat", lifespan=lifespan)
app.include_router(health_router)
