import uuid

import anthropic
import httpx
import pytest

from app.retrieval import pipeline
from app.retrieval.pipeline import NOT_FOUND
from app.retrieval.search import Hit
from env.config import settings

DOCUMENT_ID = uuid.uuid4()


def hit(position: int, text: str, similarity: float = 0.8) -> Hit:
    return Hit(
        chunk_id=uuid.uuid4(),
        document_id=DOCUMENT_ID,
        filename="Contract.pdf",
        heading_path=f"{position} Terms",
        text=text,
        page_start=position,
        page_end=position + 1,
        position_in_document=position,
        similarity=similarity,
    )


class FakeLLM:
    def __init__(self, reply="Thirty days. [c1]"):
        self.reply = reply
        self.calls = []

    def __call__(self, model, system, messages, max_tokens):
        self.calls.append({"model": model, "system": system, "messages": messages})
        return self.reply


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(pipeline, "complete", fake)
    return fake


def ask(client, question="How long is the notice?", history=()):
    return client.post("/api/chat", json={"question": question, "history": list(history)})


def test_nothing_above_the_cutoff_gives_not_found_without_calling_the_model(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [])

    response = ask(client)

    assert response.status_code == 200
    assert response.json() == {"answer": NOT_FOUND, "sources": {}}
    assert llm.calls == []


def test_answer_is_built_from_the_labelled_context_in_document_order(client, monkeypatch, llm):
    # Search returns best first; the context must be in document order.
    monkeypatch.setattr(
        pipeline,
        "search_chunks",
        lambda session, vector: [hit(7, "Notice is thirty days."), hit(3, "Terms apply.")],
    )

    body = ask(client).json()

    assert body["answer"] == "Thirty days. [c1]"
    assert body["sources"]["c1"]["page_start"] == 3
    assert body["sources"]["c2"] == {
        "label": "c2",
        "document_id": str(DOCUMENT_ID),
        "filename": "Contract.pdf",
        "page_start": 7,
        "page_end": 8,
        "heading_path": "7 Terms",
    }
    system = llm.calls[0]["system"]
    assert system.index("Terms apply.") < system.index("Notice is thirty days.")
    assert "[c2] Contract.pdf, p. 7-8, 7 Terms" in system
    assert llm.calls[0]["model"] == settings.ANSWER_MODEL


def test_unknown_ids_in_the_answer_are_dropped(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Text.")])
    llm.reply = "Real. [c1] Invented. [c9]"

    assert ask(client).json()["answer"] == "Real. [c1] Invented."


def test_only_top_n_chunks_are_used(client, monkeypatch, llm):
    hits = [hit(n, f"Chunk {n}.") for n in range(1, settings.TOP_N + 4)]
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: hits)

    assert len(ask(client).json()["sources"]) == settings.TOP_N


def test_history_is_trimmed_and_old_ids_are_removed(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Text.")])
    turns = settings.HISTORY_TURNS
    history = []
    for n in range(turns + 2):
        history += [
            {"role": "user", "content": f"Question {n}"},
            {"role": "assistant", "content": f"Answer {n}. [c4]"},
        ]

    ask(client, history=history)

    sent = llm.calls[0]["messages"]
    assert len(sent) == turns * 2 + 1
    assert sent[0] == {"role": "user", "content": "Question 2"}
    assert sent[1] == {"role": "assistant", "content": "Answer 2."}
    assert sent[-1] == {"role": "user", "content": "How long is the notice?"}


def test_a_failing_answer_call_is_a_clear_error(client, monkeypatch):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Text.")])

    def fail(*args, **kwargs):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    monkeypatch.setattr(pipeline, "complete", fail)

    response = ask(client)

    assert response.status_code == 502
    assert "could not be reached" in response.json()["detail"]


def test_an_empty_question_is_rejected(client):
    assert ask(client, question="").status_code == 422
