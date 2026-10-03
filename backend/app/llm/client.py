import re
from collections.abc import Iterator
from typing import Literal

import anthropic

from env.config import settings

KeyStatus = Literal["ok", "missing", "invalid", "unreachable"]


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.LLM_TIMEOUT_S,
        max_retries=settings.LLM_MAX_RETRIES,
    )


def check_api_key() -> KeyStatus:
    """One cheap call (list one model) that proves the key is accepted."""
    if not settings.ANTHROPIC_API_KEY:
        return "missing"
    try:
        get_client().models.list(limit=1)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        return "invalid"
    except anthropic.APIError:
        return "unreachable"
    return "ok"


def complete(model: str, system: str, messages: list[dict], max_tokens: int) -> str:
    """One Claude call; returns the text of the reply. Timeout and retries come from get_client()."""
    reply = get_client().messages.create(
        model=model, system=system, messages=messages, max_tokens=max_tokens
    )
    return "".join(block.text for block in reply.content if block.type == "text")


def stream(model: str, system: str, messages: list[dict], max_tokens: int) -> Iterator[str]:
    """One Claude call; yields the reply text as it arrives. Retries cover only the start of the call."""
    with get_client().messages.stream(
        model=model, system=system, messages=messages, max_tokens=max_tokens
    ) as reply:
        yield from reply.text_stream


def strip_json_fence(reply: str) -> str:
    """The reply without a ```json fence around it."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip())
