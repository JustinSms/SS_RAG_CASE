import json
import logging
from collections.abc import Iterator
from dataclasses import asdict
from typing import Literal

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.retrieval.citations import Source
from app.retrieval.pipeline import stream_answer

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Message] = []


def event(name: str, data) -> str:
    """One Server-Sent Event; the data is JSON, so line breaks in the answer text are safe."""
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def events(sources: dict[str, Source], text: Iterator[str]) -> Iterator[str]:
    """`sources` first, then the answer text, then `done`; `error` if the answer call fails."""
    yield event("sources", {label: asdict(source) for label, source in sources.items()})
    try:
        for piece in text:
            yield event("text", piece)
    except anthropic.APIError as error:
        yield event("error", f"The answer model could not be reached: {error.message}")
        return
    except Exception:
        log.exception("streaming the answer failed")
        yield event("error", "The answer could not be completed.")
        return
    yield event("done", {})


@router.post("")
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    history = [m.model_dump() for m in request.history]
    try:
        # The retrieval runs before the stream starts, so the session is not needed while streaming.
        sources, text = stream_answer(session, request.question.strip(), history)
    except anthropic.APIError as error:
        raise HTTPException(502, f"The answer model could not be reached: {error.message}")
    return StreamingResponse(
        events(sources, text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # the header tells nginx not to buffer
    )
