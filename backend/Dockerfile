FROM python:3.11.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend:/app \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# Dependencies first, so code changes do not reinstall them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project

# The model is downloaded at build time (pinned revision); the app never downloads at runtime.
COPY env /app/env
COPY backend/download_models.py ./
RUN python download_models.py
ENV HF_HUB_OFFLINE=1

COPY backend/app ./app
COPY backend/tests ./tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
