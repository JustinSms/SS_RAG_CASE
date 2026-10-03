import anthropic
import httpx
import pytest

from app.llm import client
from env.config import settings


class FakeModels:
    def __init__(self, error):
        self.error = error

    def list(self, limit):
        if self.error:
            raise self.error


class FakeAnthropic:
    def __init__(self, error=None):
        self.models = FakeModels(error)


def api_error(cls, status):
    request = httpx.Request("GET", "https://api.anthropic.com/v1/models")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


def check(monkeypatch, error=None, key="sk-test"):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", key)
    monkeypatch.setattr(client, "get_client", lambda: FakeAnthropic(error))
    return client.check_api_key()


def test_missing_key_makes_no_call(monkeypatch):
    def fail():
        raise AssertionError("no call expected")

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(client, "get_client", fail)
    assert client.check_api_key() == "missing"


def test_valid_key(monkeypatch):
    assert check(monkeypatch) == "ok"


def test_rejected_key(monkeypatch):
    assert check(monkeypatch, api_error(anthropic.AuthenticationError, 401)) == "invalid"


def test_network_failure(monkeypatch):
    error = anthropic.APIConnectionError(request=httpx.Request("GET", "https://x"))
    assert check(monkeypatch, error) == "unreachable"
