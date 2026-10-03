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
    EMBED_MODEL: str = "BAAI/bge-m3"
    EMBED_MODEL_REVISION: str = "5617a9f61b028005a4858fdac845db406aefb181"  # pinned commit
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Retrieval
    SIMILARITY_CUTOFF: float = 0.45
    MAX_CANDIDATES: int = 50
    TOP_N: int = 5
    RERANK_MIN_SCORE: float | None = None  # set during tuning (milestone 8)
    HISTORY_TURNS: int = 4

    # Ingestion
    MAX_CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP_TOKENS: int = 100
    CHARS_PER_TOKEN: float = 4  # token estimate for chunk sizes; no tokenizer needed
    MAX_UPLOAD_MB: int = 10
    EMBED_BATCH_SIZE: int = 32
    ENRICH_CONCURRENCY: int = 4
    ENRICH_BATCH_SIZE: int = 10

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
