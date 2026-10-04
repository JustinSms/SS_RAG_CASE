# Document Chat: App Structure and Design

Status: agreed, updated 2026-10-04. Builds on `retrieval-approach.md` and `tech-stack.md`.
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

Three containers in one `docker-compose.yml`: `web`, `api`, `db`, plus an `eval` service under a compose profile that only runs on demand (§7). One required key: `ANTHROPIC_API_KEY`.

## 2. Frontend / backend split

**Frontend (React + TypeScript + Vite, Tailwind + shadcn/ui)** owns only presentation. Three pages, detailed in `frontend-pages.md`:
- **Upload:** dropzone (PDF, max 10 MB per file, one request per file), document list with status badge and progress, duplicate dialog for the files that are already stored (*"Overwrite it?"*, resends them with `overwrite=true`), delete.
- **Chat:** message list, input, streamed answer, inline source tags `[Contract.pdf, p. 12-13, 3.1 Scope]` at the end of each sentence or short paragraph, History panel of old chats (kept in `localStorage`).
- **Database:** read-only view of documents, sections and chunks.
- A banner when `/api/health` reports a setup problem (for example a missing or invalid API key).
- No business logic. Everything it knows comes from the API.

**Backend (FastAPI)** owns everything else: parsing, chunking, enrichment, embedding, storage, retrieval, prompting, answering.

Rejected: Next.js with API routes (blurs the frontend/backend line the brief cares about, and the retrieval stack is Python anyway); Streamlit/Gradio (fast, but then the UI isn't really "built", and it's hard to defend under "build the UI yourself").

## 3. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/documents?overwrite=false` | Upload one or more PDFs as multipart field `files` (max `MAX_UPLOAD_MB` each; the browser sends one file per request). All files are checked before any is stored, so one bad file rejects the request. Returns `409` `{detail, document}` with the existing document if the hash already exists (`document: null` if the same file is twice in one request), `413` for too large, `415` for not a PDF, unreadable or encrypted. Queues processing in the background, returns `202` `{ids}`. |
| `GET` | `/api/documents` | List documents, newest first, with status, progress (`chunks_done`, `chunk_count`), `page_count`, `section_count`, size and error. The frontend polls this while anything is processing. |
| `DELETE` | `/api/documents/{id}` | Delete the document, its sections, chunks and file. `204`, or `404` for an unknown id. |
| `GET` | `/api/documents/{id}/file` | Serve the original PDF (source tags open it at the cited page). `404` for an unknown document or a missing file. |
| `GET` | `/api/documents/{id}/sections` | The sections of a document as a flat list in document order, with `parent_id`, `level`, `heading_path`, pages and `chunk_count`; the frontend builds the tree (Database page). |
| `GET` | `/api/sections/{id}/chunks` | Chunks of a section with text, context, summary, keywords, pages, `enriched` and `has_embedding` (the vector itself is not sent). `404` for an unknown section (Database page). |
| `POST` | `/api/chat` | `{question, history: [{role: user\|assistant, content}]}` from the client (no server-side conversation storage; an empty question is `422`, but a question of only spaces is accepted and runs with an empty string). Streams Server-Sent Events: first a `sources` event (label `c1`, `c2`, ... → document, pages, heading path, `cosine` and `rerank` score; both `null` for a chunk added by section selection, `rerank` also when the reranker failed), then `text` events with the answer pieces, then `done`; if the answer call fails, an `error` event instead of `done`. "Not found" is `sources` `{}`, one `text` with the not-found message, then `done`. The frontend replaces each `[c12]` with its source tag as it streams. |
| `GET` | `/api/health` | Always `200` while the api runs, with `{healthy, problems: [{code, level, message}]}`. Healthy only when the DB is reachable, the embedding model is loaded and the API key check passed (the reranker is optional and not checked). In practice `model_not_loaded` does not appear: the embedding model is loaded at startup without a fallback, so if it fails the api does not start, `web` never starts, and there is no page to show a banner on. Problems: `db_unreachable`, `model_not_loaded`, `api_key_missing` / `_invalid` / `_unreachable` (errors), `low_memory` (warning). The UI banner shows them. |

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

No conversation tables: the chat history lives in the browser (`localStorage`, the newest 10 chats) and is sent with each question. "New chat" starts a new conversation; the old one stays in the History panel. Server-side history is a "next step".

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
    sections.py         section tree and chunks of a section (Database page)
    chat.py             SSE chat endpoint
  ingestion/
    parser.py           PyMuPDF4LLM → markdown per page, styling tags (<mark>, <u>, <sup>, <sub>) removed
    sections.py         headings → section tree
    chunker.py          section → chunks with page ranges
    tokens.py           token count estimate (CHARS_PER_TOKEN) and text tails for the overlap
    enricher.py         Haiku, one call per section: context, summary, keywords (prompt-cached document)
    queue.py            one-at-a-time processing, startup recovery of interrupted documents
    pipeline.py         A1–A8 orchestration, updates document status
  retrieval/
    rewriter.py         B0: Haiku rewrites follow-ups into standalone questions
    embedder.py         bge-m3 wrapper (batch)
    reranker.py         bge-reranker-v2-m3 wrapper
    search.py           cosine search with cutoff
    selector.py         B6: LLM picks extra chunks from section summaries
    pipeline.py         B0–B8: select_context (B0–B7, with fallbacks, returns ordered, labelled context + trace), prompt and answer (streamed)
    citations.py        maps [cXX] ids to sources, drops unknown ids
  llm/
    client.py           thin Anthropic wrapper (retries with backoff, timeouts), API key check; prompt caching is set by the enricher
    prompts.py          all prompts in one place
  db/
    models.py           SQLAlchemy models above
    session.py          engine (connect timeout DB_CONNECT_TIMEOUT_S), sessions, create_all
  health.py             /api/health: DB, embedding model, API key (checked once at startup), Docker memory (MemTotal)
backend/download_models.py  downloads the two models at image build time
backend/tests/          unit and API tests, see `testing-evaluation.md` §1 (not copied into the image; the test packages pytest and httpx are, because `uv sync` installs the dev group)
```

Each pipeline file reads top to bottom like the steps in `retrieval-approach.md`, so the code maps 1:1 onto the slide you explain.

## 6. Configuration (`env/`)

Lives in its own `env/` folder next to `backend/`: `env/config.py` (pydantic-settings, every threshold and model name is a variable; the backend imports it) and `env/.env.template` (copy to `.env`, add the key). The backend image copies `env/` in.


Grouped as in `env/config.py`. Variables can be overridden in `env/.env`, with these exceptions: `DATABASE_URL` is set in `docker-compose.yml` (`environment:` wins over `env_file`); the two Hugging Face models and their revisions are fixed at image build time (see below); `MAX_UPLOAD_MB` is repeated in nginx and the frontend, so raising it alone has no effect.

| Variable | Default | Notes |
|---|---|---|
| **Secret** | | |
| `ANTHROPIC_API_KEY` | (required) | The only secret. Checked at startup; missing or invalid → shown in `/api/health` and as a UI banner |
| **Models** | | |
| `ENRICH_MODEL` | `claude-haiku-4-5` | A6 enrichment |
| `ANSWER_MODEL` | `claude-sonnet-5-5` | B8 answer |
| `REWRITE_MODEL` | `claude-haiku-4-5` | B0 follow-up rewrite |
| `SELECT_MODEL` | `claude-sonnet-5-5` | B6 section selection |
| `EMBED_MODEL` | `BAAI/bge-m3` | Fixed at image build time: downloaded by `download_models.py` without `env/.env`, and the vector size (1024) in `db/models.py` matches it. Changing it means editing the default with a matching revision, rebuilding and re-ingesting |
| `EMBED_MODEL_REVISION` | `5617a9f6…` (commit) | Pinned Hugging Face commit of the embedding model |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Fixed at image build time, like `EMBED_MODEL` |
| `RERANK_MODEL_REVISION` | `953dc6f6…` (commit) | Pinned Hugging Face commit of the reranker |
| **Retrieval** | | |
| `SIMILARITY_CUTOFF` | `0.45` | Low on purpose for bge-m3; tuned in the evaluation |
| `MAX_CANDIDATES` | `20` | Cap on chunks sent to the reranker |
| `TOP_N` | `5` | Chunks kept after reranking |
| `RERANK_MIN_SCORE` | `0.1` | Below this → "not found in your documents". Provisional until the evaluation tunes it |
| `RERANK_BATCH_SIZE` | `8` | (question, chunk) pairs per reranker batch; small because long chunks are heavy on the CPU |
| `RERANK_MAX_LENGTH` | `2048` | Tokens per (question, chunk) pair; a chunk is at most about 1,200 |
| `HISTORY_TURNS` | `4` | Past turns sent to the rewrite (B0) and the answer model (B8) |
| `REWRITE_MAX_TOKENS` | `300` | Reply size of the rewrite call; a standalone question is short |
| `SELECT_MAX_TOKENS` | `500` | Reply size of the selection call; a short list of chunk numbers |
| `MAX_SELECTED` | `10` | Cap on extra chunks the selection step adds |
| `SELECT_FALLBACK_CHARS` | `300` | Characters of text shown to the selector for a chunk without a summary (enrichment failed) |
| **Ingestion** | | |
| `MAX_CHUNK_SIZE` | `1200` | Max tokens per chunk (about two pages); also the pseudo-section size for PDFs without headings |
| `CHUNK_OVERLAP_TOKENS` | `100` | |
| `CHARS_PER_TOKEN` | `4` | Token estimate for chunk sizes (characters / 4), so no tokenizer is needed |
| `MAX_UPLOAD_MB` | `10` | Per file, checked in the dropzone and in FastAPI. nginx allows 1 MB more per request for the multipart wrapping (the browser sends one file per request) |
| `EMBED_BATCH_SIZE` | `32` | Chunks per bge-m3 batch |
| `ENRICH_CONCURRENCY` | `4` | Haiku section calls in parallel |
| `ENRICH_BATCH_SIZE` | `10` | Max chunks per Haiku call for long sections |
| `ENRICH_MAX_TOKENS` | `4000` | Reply size of one enrichment call |
| `ENRICH_DOC_MAX_TOKENS` | `150000` | Above this (estimated) document size, each call gets its section instead of the whole document; Haiku's window is 200K |
| `ENRICH_RETRIES` | `1` | Extra tries after invalid JSON or a failed call; then the chunks are stored unenriched |
| **Anthropic calls** | | |
| `LLM_TIMEOUT_S` / `LLM_MAX_RETRIES` | `60` / `3` | Every Anthropic call |
| `ANSWER_MAX_TOKENS` | `1500` | Reply size of the answer |
| **Infrastructure** | | |
| `DATABASE_URL` | set in compose | |
| `UPLOADS_DIR` | `/data/uploads` | Original PDFs, on the `uploads` volume (`/data/eval-uploads` for the eval service) |
| **Evaluation (`eval/`)** | | |
| `EVAL_DATABASE` | `docchat_eval` | The eval scripts refuse to run on any other database |
| `EVAL_CUTOFF_GRID` | `[0.3, 0.4, 0.5, 0.6]` | `SIMILARITY_CUTOFF` values tried in the tuning |
| `EVAL_RERANK_GRID` | `[0.01, 0.03, 0.1, 0.3, 0.5]` | `RERANK_MIN_SCORE` values tried |
| `EVAL_TOP_N_GRID` | `[3, 5, 8]` | `TOP_N` values tried |
| `EVAL_TUNE_TOLERANCE` | `0.01` | Settings within 1% of the questions of the best count as equally good; the pick is their middle |
| `EVAL_CONFIDENCE_Z` | `1.96` | z value for the Wilson intervals (95%) |
| **Health checks** | | |
| `MIN_MEMORY_GB` | `7.5` | Below this Docker memory, `/api/health` reports `low_memory`. "8 GB" in Docker shows as about 7.7 inside the VM |
| `DB_CONNECT_TIMEOUT_S` | `3` | Seconds to wait for a database connection (every connection, not only the health check). Below the frontend's 5 s health poll |

`MAX_CANDIDATES` exists because the cutoff alone could send hundreds of chunks to a CPU reranker; `RERANK_MIN_SCORE` because "very low" needs to be a number.

## 7. Docker layout

```
docker-compose.yml
  db    pgvector/pgvector:0.8.1-pg16, named volume pgdata, healthcheck.
        Postgres runs inside Docker; the reviewer installs nothing. Tables are created automatically on api startup, the database starts empty (no pre-seeded data)
  api   build context . with backend/Dockerfile (it copies env/ too), depends_on db (healthy), volume: uploads, healthcheck = /api/health
  web   build ./frontend (multi-stage: node build → nginx), depends_on api (healthy), proxies /api to api, port 8080
        nginx: client_max_body_size 11m (10 MB file + multipart wrapping); for /api/chat (SSE) proxy_buffering off and a 300 s read timeout (the rest of /api uses nginx's default 60 s)
  eval  profile "eval" (not started by `docker compose up`), api image with ./eval mounted, own database docchat_eval and volume eval_uploads
  all   restart: unless-stopped (not eval)
```

- Start command: `cp env/.env.template env/.env` (add key) → `docker compose up --build` → open `http://localhost:8080`.
- CPU-only PyTorch wheel in the api image to keep it a few GB smaller.
- Models: downloaded at **image build time** with pinned revisions, and `HF_HUB_OFFLINE=1` at runtime, so nothing downloads after the build. Rejected: download on first start (faster build, slower and less predictable first run).
- Everything pinned: base image tags, Python lockfile, `package-lock.json`.
- Memory: the two models need about 5 GB RAM. The README states a minimum of 8 GB Docker memory; `/api/health` reports a `low_memory` warning (shown in the banner) if Docker has less.

## 8. Repository layout

```
./
  README.md             run (incl. 8 GB Docker memory), what was built, retrieval evaluation, decisions and why, what was left out on purpose, next steps (the only README)
  LICENSE
  docker-compose.yml
  env/
    config.py           settings, one variable per threshold and model name
    .env.template       copy to .env and add ANTHROPIC_API_KEY
  docs/
    decisions.md        running log: choice · rejected option · why, plus "what broke" (feeds the README and the Q&A)
    architecture.md     the diagram and the two pipelines
    implementation-plan.md  the milestones
    design/             the agreed design (this file and the others)
  backend/  (Dockerfile, pyproject.toml, uv.lock, download_models.py, app/, tests/)
  frontend/ (Dockerfile, nginx.conf, package.json, package-lock.json, src/)
  scripts/  smoke_test.sh (clean-clone check)
  eval/                 retrieval evaluation: questions/, trees/, ingest.py, run.py, report.py (the PDFs in pdfs/ are gitignored, the folder is kept)
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
