"""B0: turn a follow-up question into a standalone one, using the recent chat history."""

import logging

from app.llm.client import complete
from app.llm.prompts import REWRITE_SYSTEM, REWRITE_USER
from env.config import settings

log = logging.getLogger(__name__)


def rewrite_question(question: str, history: list[dict]) -> str:
    """The standalone question. With no history, or if the call fails, the raw question."""
    if not history:  # nothing to refer back to
        return question
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    prompt = REWRITE_USER.format(history=transcript, question=question)
    try:
        reply = complete(
            settings.REWRITE_MODEL,
            REWRITE_SYSTEM,
            [{"role": "user", "content": prompt}],
            settings.REWRITE_MAX_TOKENS,
        ).strip()
    except Exception:
        log.exception("question rewrite failed; using the raw question")
        return question
    return reply or question
