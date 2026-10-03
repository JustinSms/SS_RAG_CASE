import pytest

from app.retrieval import rewriter
from app.retrieval.rewriter import rewrite_question
from env.config import settings

HISTORY = [
    {"role": "user", "content": "How long is the notice period?"},
    {"role": "assistant", "content": "Thirty days."},
]


@pytest.fixture
def calls(monkeypatch):
    made = []

    def fake(model, system, messages, max_tokens):
        made.append({"model": model, "messages": messages})
        return "  How long is the notice period for the lease?\n"

    monkeypatch.setattr(rewriter, "complete", fake)
    return made


def test_a_follow_up_becomes_a_standalone_question(calls):
    result = rewrite_question("and for the lease?", HISTORY)

    assert result == "How long is the notice period for the lease?"
    assert calls[0]["model"] == settings.REWRITE_MODEL
    prompt = calls[0]["messages"][0]["content"]
    assert "user: How long is the notice period?" in prompt and "and for the lease?" in prompt


def test_without_history_the_model_is_not_called(calls):
    assert rewrite_question("What is the notice period?", []) == "What is the notice period?"
    assert calls == []


def test_a_failing_call_uses_the_raw_question(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("api down")

    monkeypatch.setattr(rewriter, "complete", fail)

    assert rewrite_question("and for the lease?", HISTORY) == "and for the lease?"


def test_an_empty_reply_uses_the_raw_question(monkeypatch):
    monkeypatch.setattr(rewriter, "complete", lambda *args: "  ")

    assert rewrite_question("and for the lease?", HISTORY) == "and for the lease?"
