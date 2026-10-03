"""bge-reranker-v2-m3 wrapper. Scores (question, chunk) pairs from 0 to 1, higher is more relevant."""

import logging

from env.config import settings

log = logging.getLogger(__name__)

_reranker: "Reranker | None" = None


class Reranker:
    def __init__(self):
        from sentence_transformers import CrossEncoder  # heavy import, only when loading
        from torch.nn import Sigmoid

        self.model = CrossEncoder(
            settings.RERANK_MODEL,
            revision=settings.RERANK_MODEL_REVISION,
            max_length=settings.RERANK_MAX_LENGTH,
            activation_fn=Sigmoid(),  # raw logits are unbounded; RERANK_MIN_SCORE needs 0-1
        )

    def score(self, question: str, texts: list[str]) -> list[float]:
        pairs = [(question, text) for text in texts]
        return self.model.predict(pairs, batch_size=settings.RERANK_BATCH_SIZE).tolist()


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def load_reranker() -> None:
    """Load at startup so the first question is not slow. The reranker is optional: a failure is logged."""
    try:
        get_reranker()
    except Exception:
        log.exception("reranker could not be loaded; questions will use the cosine order")
