# Document Chat: App Structure and Design

Status: agreed, updated 2026-10-03. Builds on `retrieval-approach.md` and `tech-stack.md`.
Principle: the simplest structure that runs reliably from Docker and that every part of can be explained in the call.

## 1. Components at a glance

```
 Browser
   │
   ▼
 ┌──────────────┐   /api/*    ┌──────────────────────────────┐        ┌───────────────────┐
 │ web (nginx)  │ ──────────▶ │ api (FastAPI, Python)        │ ─────▶ │ db (Postgres +    │
 │ React SPA    │             │  • ingestion pipeline        │        │     pgvector)     │
 └──────────────┘             │  • retrieval pipeline        │        └───────────────────┘
                              │  • bge-m3 + reranker (local) │
                              │  • Anthropic client          │ ─────▶  Anthropic API
                              └──────────────────────────────┘          (Haiku, Sonnet)
                                         │
                                         ▼
                                 uploads volume (original files)
```

Three containers in one `docker-compose.yml`: `web`, `api`, `db`. One required key: `ANTHROPIC_API_KEY`.

## 2. Frontend / backend split

**Frontend (React + TypeScript + Vite, Tailwind + shadcn/ui)** owns only presentation. Three pages, detailed in `frontend-pages.md`:
- **Upload:** dropzone (PDF, max 10 MB), document list with status badge and progress, duplicate dialog (*"Overwrite it?"*, resends with `overwrite=true`), delete.
- **Chat:** message list, input, streamed answer, inline source tags `[Contract.pdf, p. 12-13, 3.1 Scope]` after each statement.
- **Database:** read-only view of documents, sections and chunks.
- A banner when `/api/health` reports a setup problem (for example a missing or invalid API key).
- No business logic. Everything it knows comes from the API.

**Backend (FastAPI)** owns everything else: parsing, chunking, enrichment, embedding, storage, retrieval, prompting, answering.

Rejected: Next.js with API routes (blurs the frontend/backend line the brief cares about, and the retrieval stack is Python anyway); Streamlit/Gradio (fast, but then the UI isn't really "built", and it's hard to defend under "build the UI yourself").

## 3. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/documents?overwrite=false` | Upload one or more PDFs (max `MAX_UPLOAD_MB` each). Returns `409` with the existing document if the hash already exists, `413`/`415` for too large or not a PDF. Queues processing in the background, returns `202` with the document ids. |
| `GET` | `/api/documents` | List documents with status and progress. The frontend polls this while anything is processing. |
| `DELETE` | `/api/documents/{id}` | Delete the document, its sections, chunks and file. |
| `GET` | `/api/documents/{id}/file` | Serve the original PDF (source tags open it at the cited page). |
| `GET` | `/api/documents/{id}/sections` | Section tree of a document (Database page). |
| `GET` | `/api/sections/{id}/chunks` | Chunks of a section with context, summary, keywords, pages (Database page). |
| `POST` | `/api/chat` | Question + recent history from the client (no server-side conversation storage). Streams Server-Sent Events: first a `sources` event (chunk id → document, pages, headings), then the answer text, then `done`. The frontend replaces each `[c12]` with its source tag as it streams. |
| `GET` | `/api/health` | Healthy only when the DB is reachable, the models are loaded and the API key check passed. Reports setup problems (missing or invalid key, low memory) for the UI banner. |

**Background processing:** a simple in-process queue that processes one document at a time, with status stored on the document row. On startup, documents left in `processing` are marked `failed` ("interrupted, please re-upload").
Rejected: Celery/RQ + Redis (a 4th and 5th container for a single-user demo; worth naming as "next step for multi-user").

**Streaming:** SSE, because it's one-directional and works with a plain `fetch`. Rejected: WebSockets (two-way isn't needed).

## 4. Data model (Postgres + pgvector)

```
documents
  id (uuid) · filename · sha256 (unique) · size_bytes · status (processing|ready|failed)
  error · page_count · chunk_count · chunks_done · created_at

sections
  id · document_id → documents · parent_id → sections (nullable)
  heading · level · heading_path (text, e.g. "2 Scope > 2.1 Data")
  position (order in document) · page_start · page_end

chunks
  id · document_id → documents · section_id → sections
  position_in_section · position_in_document
  text · context · summary · keywords (text[]) · enriched (bool)
  page_start · page_end
  embedding vector(1024)          -- bge-m3 dense size
  index: HNSW on embedding (vector_cosine_ops)
```

No conversation tables: the chat history lives in the browser and is sent with each question. "New chat" clears it. Server-side history is a "next step".

- `ON DELETE CASCADE` from documents, so delete is one statement. Overwrite ingests the new version first, then deletes the old one in one transaction, so a failed overwrite keeps the old document.
- `enriched = false` marks chunks whose Haiku enrichment failed (they're stored and embedded as plain text); the Database page shows it.
- `position_in_document` gives "document order" for step B7 without extra sorting logic.
- `chunks_done / chunk_count` drives the progress bar on the Upload page.
- Schema created at startup with SQLAlchemy `create_all`. Rejected for now: Alembic migrations (there is one schema version; it's a "next step").

## 5. Backend layout and flow

```
backend/app/
  main.py               FastAPI app, startup (create tables, load models)
  api/
    documents.py        upload, list, delete, file
    chat.py             SSE chat endpoint
  ingestion/
    parser.py           PyMuPDF4LLM → markdown per page
    sections.py         headings → section tree
    chunker.py          section → chunks with page ranges
    enricher.py         Haiku, one call per section: context, summary, keywords (prompt-cached document)
    queue.py            one-at-a-time processing, startup recovery of interrupted documents
    pipeline.py         A1–A8 orchestration, updates document status
  retrieval/
    rewriter.py         B0: Haiku rewrites follow-ups into standalone questions
    embedder.py         bge-m3 wrapper (batch)
    reranker.py         bge-reranker-v2-m3 wrapper
    search.py           cosine search with cutoff
    selector.py         B6: LLM picks extra chunks from section summaries
    pipeline.py         B0–B7 orchestration with fallbacks, returns ordered, labelled context + trace
    citations.py        maps [cXX] ids to sources, drops unknown ids
  llm/
    client.py           thin Anthropic wrapper (retries with backoff, timeouts, caching flags)
    prompts.py          all prompts in one place
  db/
    models.py           SQLAlchemy models above
    session.py
  health.py             startup checks: DB, models, API key, available memory
backend/tests/          unit and API tests, see `testing-evaluation.md` §1
```

Each pipeline file reads top to bottom like the steps in `retrieval-approach.md`, so the code maps 1:1 onto the slide you explain.

## 6. Configuration (`env/`)

Lives in its own `env/` folder next to `backend/`: `env/config.py` (pydantic-settings, every threshold and model name is a variable; the backend imports it) and `env/.env.template` (copy to `.env`, add the key). The backend image copies `env/` in.


| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | The only secret. Checked at startup; missing or invalid → shown in `/api/health` and as a UI banner |
| `ENRICH_MODEL` | `claude-haiku-4-5` | |
| `ANSWER_MODEL` | `claude-sonnet-5-5` | Also used for B6 selection |
| `EMBED_MODEL` | `BAAI/bge-m3` | |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | |
| `SIMILARITY_CUTOFF` | `0.45` | Low on purpose for bge-m3; tuned in the evaluation |
| `MAX_CANDIDATES` | `50` | Cap on chunks sent to the reranker |
| `TOP_N` | `5` | |
| `RERANK_MIN_SCORE` | set during tuning | Below this → "not found in your documents" |
| `MAX_CHUNK_SIZE` | `1200` | Max tokens per chunk (about two pages); also the pseudo-section size for PDFs without headings |
| `CHUNK_OVERLAP_TOKENS` | `100` | |
| `MAX_UPLOAD_MB` | `10` | Same limit in nginx, FastAPI and the dropzone |
| `EMBED_BATCH_SIZE` | `32` | Chunks per bge-m3 batch |
| `ENRICH_CONCURRENCY` | `4` | Haiku section calls in parallel |
| `ENRICH_BATCH_SIZE` | `10` | Max chunks per Haiku call for long sections |
| `LLM_TIMEOUT_S` / `LLM_MAX_RETRIES` | `60` / `3` | Every Anthropic call |
| `HISTORY_TURNS` | `4` | Past turns sent to the answer model |
| `DATABASE_URL` | set in compose | |

`MAX_CANDIDATES` exists because the cutoff alone could send hundreds of chunks to a CPU reranker; `RERANK_MIN_SCORE` because "very low" needs to be a number.

## 7. Docker layout

```
docker-compose.yml
  db    pgvector/pgvector:pg16, named volume pgdata, healthcheck.
        Postgres runs inside Docker; the reviewer installs nothing. Tables are created automatically on api startup, the database starts empty (no pre-seeded data)
  api   build ./backend, depends_on db (healthy), volume: uploads, healthcheck = /api/health
  web   build ./frontend (multi-stage: node build → nginx), depends_on api (healthy), proxies /api to api, port 8080
        nginx: client_max_body_size 10m; proxy_buffering off for /api/chat (SSE)
  all   restart: unless-stopped
```

- Start command: `cp env/.env.template env/.env` (add key) → `docker compose up --build` → open `http://localhost:8080`.
- CPU-only PyTorch wheel in the api image to keep it a few GB smaller.
- Models: downloaded at **image build time** with pinned revisions, and `HF_HUB_OFFLINE=1` at runtime, so nothing downloads after the build. Rejected: download on first start (faster build, slower and less predictable first run).
- Everything pinned: base image tags, Python lockfile, `package-lock.json`.
- Memory: the two models need about 5 GB RAM. The README states a minimum of 8 GB Docker memory; the api warns at startup if less is available.

## 8. Repository layout

```
document-chat/
  README.md             run (incl. 8 GB Docker memory), what was built, decisions and why, what was left out on purpose, next steps
  docker-compose.yml
  env/
    config.py           settings, one variable per threshold and model name
    .env.template       copy to .env and add ANTHROPIC_API_KEY
  docs/
    decisions.md        running log: choice · rejected option · why, plus "what broke" (feeds the README and the Q&A)
    architecture.md     the diagram and the two pipelines
  backend/  (Dockerfile, pyproject.toml, app/, tests/)
  frontend/ (Dockerfile, nginx.conf, package.json, src/)
  eval/                 later: question set + hit rate / refusal rate script (source overlap)
```

The brief HTML and the old `rag/` folder stay out of the repo (confidential, and its code is not reused; only ideas from an earlier review carry over).

## 9. Suggested build order (commit as you go)

1. Skeleton: compose with three containers, healthchecks, `/api/health` with the API key check, a page that shows "backend ready" or the setup banner. nginx upload limit and SSE settings in from the start. Start `docs/decisions.md`.
2. Upload → checks → parse → sections → chunks → store, without enrichment. Processing queue and startup recovery. Document list in the UI.
3. Embed → cosine search → answer with citations. **The happy path works end to end here.** Tune `SIMILARITY_CUTOFF` on a real PDF. Test from a clean clone.
4. Add enrichment (Haiku, per section), follow-up rewrite, reranker, section selection (B6), "not found" handling, each with its fallback.
5. Streaming with the `sources` event, duplicate dialog with safe overwrite, progress bar, error states. **Database page** and its two endpoints.
6. README (including the 8 GB memory requirement), decision log, second clean-clone test.
7. Extras only if time is left: citation highlighting, then eval numbers.

Run the clean-clone smoke test after every step from step 3, and before the demo.

## 10. Decisions

- **Chat scope:** always search all documents.
- **File types:** PDF only, max 10 MB.
- **Follow-up questions:** rewrite into a standalone question with Haiku before retrieval, using recent chat history.
- **Model download:** at image build time, so the app is ready right after `docker compose up --build`.
- **Local models over paid services:** one API key for reviewers (see `tech-stack.md`).
- **Stability first:** optional steps (rewrite, rerank, selection, enrichment) fall back instead of failing; only the answer call is required.
- **No reuse of the old `rag/` code.**
