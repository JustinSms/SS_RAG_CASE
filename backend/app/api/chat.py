from typing import Literal

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.retrieval.pipeline import answer_question

router = APIRouter(prefix="/api/chat")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Message] = []


class SourceOut(BaseModel):
    label: str
    document_id: str
    filename: str
    page_start: int
    page_end: int
    heading_path: str


class ChatResponse(BaseModel):
    answer: str
    sources: dict[str, SourceOut]


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    history = [m.model_dump() for m in request.history]
    try:
        return answer_question(session, request.question.strip(), history)
    except anthropic.APIError as error:
        raise HTTPException(502, f"The answer model could not be reached: {error.message}")
