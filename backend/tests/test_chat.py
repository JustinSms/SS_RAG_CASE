import uuid

import anthropic
import httpx
import pytest

from app.retrieval import pipeline, reranker
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


class ScoresByText:
    """A reranker that scores each chunk from a fixed table."""

    def __init__(self, scores):
        self.scores = scores

    def score(self, question, texts):
        return [self.scores[t] for t in texts]


def use_reranker(monkeypatch, fake):
    monkeypatch.setattr(reranker, "_reranker", fake)


def test_the_reranker_decides_which_chunks_are_kept(client, monkeypatch, llm):
    hits = [hit(n, f"Chunk {n}.") for n in range(1, settings.TOP_N + 3)]  # cosine order: 1, 2, 3, ...
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: hits)
    scores = {h.text: 0.5 for h in hits}
    scores["Chunk 7."] = 0.95  # the last by cosine is the best by rerank
    use_reranker(monkeypatch, ScoresByText(scores))

    sources = ask(client).json()["sources"]

    assert len(sources) == settings.TOP_N
    assert 7 in {s["page_start"] for s in sources.values()}


def test_the_trace_lists_the_chunk_ids_after_each_stage(monkeypatch):
    hits = [hit(n, f"Chunk {n}.") for n in range(1, settings.TOP_N + 3)]
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: hits)
    scores = {h.text: 0.5 for h in hits}
    scores["Chunk 7."] = 0.95
    use_reranker(monkeypatch, ScoresByText(scores))

    _, trace = pipeline.select_context(None, "question")

    assert trace.candidates == [h.chunk_id for h in hits]
    assert trace.reranked[0] == hits[-1].chunk_id
    assert len(trace.top_n) == settings.TOP_N
    assert trace.best_rerank_score == 0.95
    assert not trace.not_found


def test_a_failing_reranker_keeps_the_cosine_order_and_still_answers(client, monkeypatch, llm):
    hits = [hit(n, f"Chunk {n}.") for n in range(1, settings.TOP_N + 3)]
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: hits)

    class Broken:
        def score(self, question, texts):
            raise RuntimeError("model crashed")

    use_reranker(monkeypatch, Broken())

    body = ask(client).json()
    _, trace = pipeline.select_context(None, "question")

    assert body["answer"] == "Thirty days. [c1]"
    assert {s["page_start"] for s in body["sources"].values()} == set(range(1, settings.TOP_N + 1))
    assert trace.reranked is None
    assert trace.top_n == [h.chunk_id for h in hits[: settings.TOP_N]]


def test_a_reranker_that_cannot_load_keeps_the_cosine_order(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Text.")])

    def cannot_load():
        raise OSError("model files missing")

    monkeypatch.setattr(pipeline, "get_reranker", cannot_load)

    assert ask(client).json()["answer"] == "Thirty days. [c1]"


def test_a_low_rerank_score_gives_not_found_without_calling_the_model(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Unrelated text.")])
    use_reranker(monkeypatch, ScoresByText({"Unrelated text.": settings.RERANK_MIN_SCORE / 2}))

    response = ask(client)

    assert response.json() == {"answer": NOT_FOUND, "sources": {}}
    assert llm.calls == []


def test_a_score_at_the_minimum_is_still_answered(client, monkeypatch, llm):
    monkeypatch.setattr(pipeline, "search_chunks", lambda session, vector: [hit(1, "Text.")])
    use_reranker(monkeypatch, ScoresByText({"Text.": settings.RERANK_MIN_SCORE}))

    assert ask(client).json()["answer"] == "Thirty days. [c1]"
    assert len(llm.calls) == 1
