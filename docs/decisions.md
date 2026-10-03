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
- Frontend toolchain: exact-pinned versions in `package.json` plus `package-lock.json`; TypeScript 6.0.3, not 7. `typescript-eslint` 8.71 only supports TypeScript below 6.1, and lint matters more than the newest compiler. Move to 7 when `typescript-eslint` supports it.
- shadcn components are added with the CLI and then edited: the CLI v4 wrote `import { cn } from "cn"` and added an unrelated npm package `cn` plus the `radix-ui` umbrella. Replaced by `@/lib/utils` and `@radix-ui/react-slot`, both pinned.
- Frontend tests use vitest + Testing Library with `fetch` stubbed (no network, no api needed). `npm test`.
- The browser polls `/api/health` every 5 s (`HEALTH_POLL_MS`), so the banner clears after the user fixes the key and restarts the api, without a reload. An unreachable api shows the same red banner.
- `web` serves on 8080 (nginx container port 80); the `api` port 8000 is no longer published. For `npm run dev`, publish it again or run uvicorn locally (vite proxies `/api` to `localhost:8000`).
- nginx 10m limit duplicates `MAX_UPLOAD_MB` (nginx cannot read pydantic settings); noted in `nginx.conf`. Base images pinned: `node:24.14.1-alpine`, `nginx:1.30.0-alpine`.
- Upload checks run on all files of a request before any is stored; one bad file rejects the request. A `409` carries the existing document as `document` in the body (a file repeated inside one request gets `409` with `document: null`). PDFs are opened with PyMuPDF to detect encryption; a file PyMuPDF cannot open is `415`. Order of checks: size (`413`), header (`415`), readable/encrypted (`415`).
- Files are stored as `UPLOADS_DIR/<document id>.pdf`; the original name lives only in the database, so odd file names never touch the file system.
- Queue: one daemon worker thread over `queue.Queue`. A crash in the pipeline marks that document `failed` with the error and the worker carries on with the next one.
- Unit tests use in-memory SQLite, not Postgres: `Vector` and `ARRAY` columns have JSON variants for SQLite (in `db/models.py`) and the HNSW index is Postgres-only. Cascade, the pgvector extension and the index were checked by hand against the real `db` container. Rejected: tests that need the `db` container (pytest would then not run on a laptop without Docker).
- `pgvector`, `python-multipart` and `pymupdf` added to the backend (pinned by `uv.lock`); PyMuPDF is reused for parsing in milestone 4.

## What broke

- Milestone 1: the stock Python `.gitignore` had `env/` and `ENV/` (virtualenv folders). Git on macOS matches case-insensitively, so both hid our `env/` config folder. Replaced with `env/.env`.
- Milestone 1: the memory warning fired on Docker set to 8 GB because the VM reports about 7.7 GB. `MIN_MEMORY_GB` default is 7.5.
- Milestone 1: uvicorn in the container could not import `env.config`; pytest's `pythonpath` setting does not apply to uvicorn. Fixed with `PYTHONPATH` in the Dockerfile.
- Milestone 2: the Python `lib/` rule in `.gitignore` also hid `frontend/src/lib`. Scoped it to `/backend/lib/`. `node_modules/` was not ignored yet.
