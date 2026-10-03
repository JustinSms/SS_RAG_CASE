"""bge-m3 wrapper. Loaded once at startup; vectors are normalised, so cosine similarity = dot product."""

from env.config import settings

_embedder: "Embedder | None" = None


class Embedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer  # heavy import, only when loading

        self.model = SentenceTransformer(
            settings.EMBED_MODEL, revision=settings.EMBED_MODEL_REVISION
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts, batch_size=settings.EMBED_BATCH_SIZE, normalize_embeddings=True
        )
        return vectors.tolist()


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def embedder_loaded() -> bool:
    return _embedder is not None
