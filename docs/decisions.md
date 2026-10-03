# Decision log

Running log: choice, rejected option, why. Also records what broke. Feeds the README ("decisions and why") and the Q&A in the call.
Seeded from the planning phase, 2026-10-03.

## Key decision: retrieval is evaluated by source overlap only; the answers are not evaluated yet

**Decision.** The evaluation (`eval/`) measures only the overlap between the sources the system retrieves and the gold sources (document and heading) for each question, as **accuracy, precision and recall**. It does not generate answers and does not grade them.

**Why.** It is a quick win: no hand grading (about an hour for 120 answers), no LLM judge to defend, deterministic and cheap, and it still shows whether the right passages are found, which is the part the pipeline controls.

**What this does not tell us.** Good source overlap is necessary for a good answer but not sufficient: the model can still misread, ignore or over-extend the context. Citation validity and precision are also not measured here.

**Next step (must be done).** Evaluate the actual answers, by hand (correct / partial / wrong against a reference answer) or with an LLM judge, together with citation validity and precision. Add `reference_answer` to the question files at that point. The README and the call must say clearly that answer quality is not yet measured.

**Rejected for now.** Hand grading of all answers (too slow for the first pass); LLM judge (one more thing to defend, and it needs validating against hand grades first).

## Other decisions

(Move the choice and rejected option for each item from `design/tech-stack.md`, `design/app-structure.md` and `design/frontend-pages.md` here as the build progresses. Already agreed:)

- Own frontend and backend; old `rag/` code not reused, only ideas.
- Local bge-m3 and bge-reranker-v2-m3 instead of paid services: one API key for reviewers. Rejected: Voyage.
- One Haiku call per section for enrichment. Rejected: one call per chunk (slow), Message Batches API (asynchronous, breaks a live upload).
- Postgres + pgvector. Rejected: Chroma/LanceDB/Qdrant.
- FastAPI + React, SSE for streaming. Rejected: Next.js API routes, Streamlit/Gradio, WebSockets, Celery/Redis.
- Neighbours vs. LLM section selection comparison: out of scope, a next step.
- Optional steps (rewrite, rerank, section selection, enrichment) fall back instead of failing; only the answer call is required.
- `SIMILARITY_CUTOFF` default 0.45 (lowered from 0.70): bge-m3 cosine scores for relevant passages often sit around 0.5-0.7, so the cutoff only removes clear noise and the reranker does the real filtering. Tuned in the evaluation.
- Dense search only in v1. Next step: keyword search (BM25 via Postgres full-text search) as a hybrid, compared in the evaluation. Rejected for now: one more retrieval path to tune before the happy path works.
- No OCR in v1; scanned PDFs are rejected as "no text found". Next step: OCR for pages without a text layer (for example Tesseract via PyMuPDF).
- `/api/health` always returns 200 while the app is up; the body carries `healthy` and a `problems` list (`level` error or warning). A non-200 would make the `api` container unhealthy, and then `web` (which waits for it) could never start and show the setup banner. The compose healthcheck therefore only proves the app answers.
- API key check: one `models.list(limit=1)` call at startup through `llm/client.py`, result cached until restart. Rejected: a tiny message call (costs tokens, needs a prompt). Auth errors mean "invalid", other API errors mean "unreachable".
- Memory check reads `MemTotal` from `/proc/meminfo` (the Docker VM), not available memory, which fluctuates. Skipped when the file does not exist.
- `RERANK_MIN_SCORE` defaults to `None` until it is tuned in milestone 8. `ANTHROPIC_API_KEY` defaults to empty so a missing key shows up in health instead of crashing at startup.
- Backend image: build context is the repo root (so `env/` can be copied in), `uv sync --frozen` from `uv.lock`, pinned `python:3.11.15-slim` and `uv:0.10.12`. `env/.env` is kept out of the image by `.dockerignore`; compose passes it in with `env_file` (optional, so a missing file shows the missing-key problem).

## What broke

- Milestone 1: the stock Python `.gitignore` had `env/` and `ENV/` (virtualenv folders). Git on macOS matches case-insensitively, so both hid our `env/` config folder. Replaced with `env/.env`.
- Milestone 1: the memory warning fired on Docker set to 8 GB because the VM reports about 7.7 GB. `MIN_MEMORY_GB` default is 7.5.
- Milestone 1: uvicorn in the container could not import `env.config`; pytest's `pythonpath` setting does not apply to uvicorn. Fixed with `PYTHONPATH` in the Dockerfile.
