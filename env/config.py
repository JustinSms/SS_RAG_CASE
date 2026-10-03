from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env", extra="ignore"
    )

    # The only secret. Empty means "missing"; /api/health reports it.
    ANTHROPIC_API_KEY: str = ""

    # Models
    ENRICH_MODEL: str = "claude-haiku-4-5"
    ANSWER_MODEL: str = "claude-sonnet-5-5"
    REWRITE_MODEL: str = "claude-haiku-4-5"
    SELECT_MODEL: str = "claude-sonnet-5-5"
    EMBED_MODEL: str = "BAAI/bge-m3"
    EMBED_MODEL_REVISION: str = "5617a9f61b028005a4858fdac845db406aefb181"  # pinned commit
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_MODEL_REVISION: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"  # pinned commit

    # Retrieval
    SIMILARITY_CUTOFF: float = 0.45
    MAX_CANDIDATES: int = 50
    TOP_N: int = 5
    RERANK_MIN_SCORE: float = 0.1  # reranker score is 0-1; provisional, tuned in the evaluation
    RERANK_BATCH_SIZE: int = 8  # pairs per reranker batch; small, long chunks are heavy on CPU
    RERANK_MAX_LENGTH: int = 2048  # tokens per (question, chunk) pair; a chunk is at most about 1,200
    HISTORY_TURNS: int = 4
    REWRITE_MAX_TOKENS: int = 300  # a standalone question is short
    SELECT_MAX_TOKENS: int = 500  # reply is a short list of chunk numbers
    MAX_SELECTED: int = 10  # cap on extra chunks added by the selection step
    SELECT_FALLBACK_CHARS: int = 300  # text shown to the selector for a chunk that has no summary

    # Ingestion
    MAX_CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP_TOKENS: int = 100
    CHARS_PER_TOKEN: float = 4  # token estimate for chunk sizes; no tokenizer needed
    MAX_UPLOAD_MB: int = 10
    EMBED_BATCH_SIZE: int = 32
    ENRICH_CONCURRENCY: int = 4
    ENRICH_BATCH_SIZE: int = 10
    ENRICH_MAX_TOKENS: int = 4000  # reply size of one enrichment call
    ENRICH_DOC_MAX_TOKENS: int = 150_000  # above this the section is sent, not the document (Haiku window is 200K)
    ENRICH_RETRIES: int = 1  # extra tries after invalid JSON or a failed call

    # Anthropic calls
    LLM_TIMEOUT_S: float = 60
    LLM_MAX_RETRIES: int = 3
    ANSWER_MAX_TOKENS: int = 1500

    # Infrastructure
    DATABASE_URL: str = "postgresql+psycopg://docchat:docchat@localhost:5432/docchat"
    UPLOADS_DIR: str = "/data/uploads"

    # Health checks
    MIN_MEMORY_GB: float = 7.5  # "8 GB" Docker shows as about 7.7 inside the VM
    DB_CHECK_TIMEOUT_S: int = 3


settings = Settings()
