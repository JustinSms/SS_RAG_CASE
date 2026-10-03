import math

from env.config import settings


def count_tokens(text: str) -> int:
    """Estimate the token count from the length (see CHARS_PER_TOKEN)."""
    return math.ceil(len(text) / settings.CHARS_PER_TOKEN)
