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
