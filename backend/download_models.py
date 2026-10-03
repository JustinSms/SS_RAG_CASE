"""Run once while the image is built, so nothing is downloaded when the app runs."""

from huggingface_hub import snapshot_download

from env.config import settings

# Only what sentence-transformers needs; the repo also holds ONNX copies and other heads.
FILES = [
    "*.json",
    "sentencepiece.bpe.model",
    "pytorch_model.bin",
]

snapshot_download(settings.EMBED_MODEL, revision=settings.EMBED_MODEL_REVISION, allow_patterns=FILES)
