"""Run once while the image is built, so nothing is downloaded when the app runs."""

from huggingface_hub import snapshot_download

from env.config import settings

# Only what sentence-transformers needs; the embedding repo also holds ONNX copies and other heads.
EMBED_FILES = [
    "*.json",
    "sentencepiece.bpe.model",
    "pytorch_model.bin",
]
RERANK_FILES = [
    "*.json",
    "sentencepiece.bpe.model",
    "model.safetensors",
]

snapshot_download(settings.EMBED_MODEL, revision=settings.EMBED_MODEL_REVISION, allow_patterns=EMBED_FILES)
snapshot_download(settings.RERANK_MODEL, revision=settings.RERANK_MODEL_REVISION, allow_patterns=RERANK_FILES)
