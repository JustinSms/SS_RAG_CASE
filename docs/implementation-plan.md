# Implementation Plan

The app is built in 14 small milestones. Each milestone is one branch, a few commits, and one merge into `main` after you have checked it. The order follows the build order in `design/app-structure.md` §9, split into smaller pieces. The happy path (upload a PDF, ask a question, get a cited answer) works at the end of milestone 6.

## How to work with Claude Code

For each milestone:

1. `git checkout main && git pull && git checkout -b <branch>`
2. Give Claude Code this prompt (replace the number):

   > Read `CLAUDE.md` and milestone N in `docs/implementation-plan.md`, plus the docs it lists. Propose a short plan first, then build only what is in scope. Commit in small steps. Run the tests before each commit. When you are done, tell me how to run the check.

3. Review the diff, run the **Check** yourself, then merge into `main` (a merge commit or fast-forward, no squash).
4. If something broke on the way or a decision changed, make sure it is in `docs/decisions.md` before merging.

Plan mode in Claude Code (Shift+Tab) is a good fit for step 2: you see the plan before any file is written.

From milestone 6 on, also run the clean-clone smoke test before merging: `scripts/smoke_test.sh` (created in milestone 6).

## Overview

| # | Branch | Result |
|---|---|---|
| 0 | `main` | Docs and repo basics in place |
| 1 | `m1-backend-skeleton` | `api` + `db` containers, `/api/health` |
| 2 | `m2-frontend-skeleton` | `web` container, themed app shell, setup banner |
| 3 | `m3-upload-api` | Upload, list, delete, file endpoints; processing queue |
| 4 | `m4-parse-and-chunk` | PDF → sections → chunks stored in the DB |
| 5 | `m5-upload-page` | Upload page with document list |
| 6 | `m6-happy-path` | Embeddings, search, cited answer, basic chat page. **Happy path works** |
| 7 | `m7-enrichment` | Haiku context, summary, keywords per chunk |
| 8 | `m8-rerank-not-found` | Reranker and "not found in your documents" |
| 9 | `m9-rewrite-and-selection` | Follow-up rewrite, section selection, combine in document order |
| 10 | `m10-streaming-chat` | SSE streaming with the `sources` event, inline source tags |
| 11 | `m11-upload-polish` | Duplicate dialog, safe overwrite, progress bar, error states |
| 12 | `m12-database-page` | Read-only Database page and its two endpoints |
| 13 | `m13-readme` | README, `docs/architecture.md`, second clean-clone test |
| 14 | `m14-evaluation` | `eval/` script and `eval/results.md` (extra) |

---

## 0. Repo basics (directly on `main`)

**Goal:** the repo holds the plan and the basics, so Claude Code has everything from the first branch.

**You do this by hand:**
- Copy this folder's contents into the repo root (`CLAUDE.md`, `docs/`).
- Add a `.gitignore` (Python, Node, `env/.env`, `*.pdf` outside test fixtures, `.venv`, `node_modules`, `dist`).
- Add a one-line `README.md` placeholder.
- Commit: "Add design docs and implementation plan".

**Check:** the repo on GitHub shows `CLAUDE.md`, `docs/`, `.gitignore`. The case brief HTML and the old `rag/` folder are **not** in it.

---

## 1. Backend skeleton (`m1-backend-skeleton`)

**Goal:** `docker compose up --build` starts Postgres and a FastAPI app that reports its health.

**Read:** `design/app-structure.md` §1, §3 (`/api/health` row), §6, §7, §8.

**Build:**
- `env/config.py` with **all** variables from `app-structure.md` §6 and their defaults; `env/.env.template`.
- `docker-compose.yml` with `db` (`pgvector/pgvector:pg16`, named volume, healthcheck) and `api` (healthcheck on `/api/health`, `depends_on: db healthy`, `restart: unless-stopped`, uploads volume).
- `backend/` with Dockerfile, `pyproject.toml` + lockfile, `app/main.py`, `app/db/session.py`, `app/health.py`.
- `/api/health`: DB reachable, API key present and valid (one cheap call at startup, result cached), available memory (warning below 8 GB). Returns the problems as a list for the UI banner.
- `pytest` set up, with a first test for `/api/health` reporting a missing key.

**Out of scope:** frontend, tables, models, any pipeline code.

**Suggested commits:** config and env template → compose with db → FastAPI app and Dockerfile → health checks → tests.

**Check:**
- `cp env/.env.template env/.env`, add your key, `docker compose up --build`; `docker compose ps` shows both containers healthy.
- `curl localhost:8000/api/health` (or the port you expose for now) shows healthy.
- Remove the key, restart `api`: health reports the missing key.
- `docker compose run --rm api pytest` passes.

---

## 2. Frontend skeleton (`m2-frontend-skeleton`)

**Goal:** `http://localhost:8080` shows the themed app shell and whether the backend is ready.

**Read:** `design/frontend-pages.md` (Layout, Frontend layout), `design/globals.css`, `design/app-structure.md` §2, §7.

**Build:**
- `frontend/` with Vite + React + TypeScript, Tailwind v4, shadcn/ui (components copied into `components/ui/`), `globals.css` from `docs/design/globals.css`, Inter font.
- App shell: dark top bar, three nav links (Chat `/`, Upload `/upload`, Database `/database`), empty placeholder pages.
- `api/client.ts` with a typed `getHealth()`; `SetupBanner` shown when health reports problems; the Chat placeholder shows "Backend ready".
- `frontend/Dockerfile` (multi-stage: node build → nginx) and `nginx.conf`: serves the SPA, proxies `/api` to `api`, `client_max_body_size 10m`, `proxy_buffering off` for `/api/chat`.
- `web` service in compose, port 8080, `depends_on: api healthy`. The `api` port no longer needs to be exposed.

**Out of scope:** real page content.

**Suggested commits:** Vite + Tailwind + shadcn setup → theme and app shell → health client and banner → Dockerfile, nginx, compose.

**Check:**
- `docker compose up --build`, open `http://localhost:8080`: dark header, red active link, "Backend ready".
- Without the key: the red banner says what is wrong.
- `npm run build` and `npm run lint` pass.

---

## 3. Upload API and queue (`m3-upload-api`)

**Goal:** PDFs can be uploaded, listed, downloaded and deleted through the API. Processing is a stub for now.

**Read:** `design/app-structure.md` §3, §4; `design/retrieval-approach.md` A1-A2; `design/testing-evaluation.md` §1 (API row).

**Build:**
- `db/models.py`: `documents`, `sections`, `chunks` exactly as in §4 (incl. `vector(1024)` and the HNSW index), created with `create_all` at startup, `ON DELETE CASCADE`.
- `api/documents.py`: `POST /api/documents` (PDF header check, `MAX_UPLOAD_MB`, encrypted PDF rejected, sha256 → `409` with the existing document), `GET /api/documents`, `DELETE /api/documents/{id}` (row + file), `GET /api/documents/{id}/file`.
- `ingestion/queue.py`: in-process queue, one document at a time; startup marks leftover `processing` documents as `failed` ("interrupted, please re-upload").
- `ingestion/pipeline.py` as a stub that sets the status to `ready`.
- Tests: `202`, `409`, `413`, `415`, delete cascades, startup recovery.

**Out of scope:** parsing and chunking, `overwrite=true` (milestone 11), any frontend.

**Check:**
- `curl -F "files=@some.pdf" localhost:8080/api/documents` returns `202`; again returns `409`; `GET /api/documents` lists it as `ready`; `DELETE` removes it.
- A `.txt` renamed to `.pdf` returns `415`.
- `pytest` passes.

---

## 4. Parse, sections, chunks (`m4-parse-and-chunk`)

**Goal:** an uploaded PDF ends up as a section tree and chunks in the database (no enrichment, no embeddings yet).

**Read:** `design/retrieval-approach.md` A3-A5, A8; `design/app-structure.md` §4, §5; `design/testing-evaluation.md` §1 (`sections.py`, `chunker.py` rows).

**Build:**
- `ingestion/parser.py`: PyMuPDF4LLM → markdown per page, keeping page numbers. PDFs without text rejected as "no text found".
- `ingestion/sections.py`: headings → tree with `parent_id`, `level`, `heading_path`, `position`, page range. Text before the first heading goes into a root section. No headings → pseudo-sections of `MAX_CHUNK_SIZE`.
- `ingestion/chunker.py`: paragraph boundaries, at most `MAX_CHUNK_SIZE` tokens, `CHUNK_OVERLAP_TOKENS` overlap, never crosses a section, correct page ranges, `position_in_section` and `position_in_document`.
- `ingestion/pipeline.py`: parse → sections → chunks → store, updating `status`, `page_count`, `chunk_count`.
- Tests for sections and chunker from the table in `testing-evaluation.md`, using small generated markdown, not real PDFs.

**Out of scope:** enrichment, embeddings, frontend.

**Check:**
- Upload one of your real PDFs. In `docker compose exec db psql ...`, the section headings look like the PDF's table of contents, and no chunk is longer than about two pages.
- Note in `docs/decisions.md` anything the parser gets wrong on your PDF.
- `pytest` passes.

---

## 5. Upload page (`m5-upload-page`)

**Goal:** documents can be uploaded, watched and deleted in the UI.

**Read:** `design/frontend-pages.md` §1.

**Build:**
- `Dropzone` (click or drag, PDF only, max 10 MB, checked in the browser first), `DocumentList` (name, pages, status badge, delete), polling `GET /api/documents` every few seconds while anything is processing, error text for failed documents.
- Typed client functions for upload, list, delete.
- A `409` shows a simple message for now ("already uploaded"); the overwrite dialog comes in milestone 11.

**Out of scope:** overwrite dialog, progress bar.

**Check:** upload two PDFs at once in the browser; both go processing → ready; a 15 MB file and a `.docx` are rejected with a message; delete works; `npm run build` passes.

---

## 6. Happy path: embed, search, answer (`m6-happy-path`)

**Goal:** ask a question in the browser and get an answer with sources. **This is the most important milestone.**

**Read:** `design/retrieval-approach.md` A7, B1, B2, B4 (not-found on cutoff only), B8; `design/tech-stack.md` (Embeddings, Chat LLMs); `design/app-structure.md` §3 (`/api/chat`), §5, §7 (models at build time); `design/frontend-pages.md` §2.

**Build:**
- `api` Dockerfile: CPU-only PyTorch; bge-m3 downloaded at **build time** with a pinned revision; `HF_HUB_OFFLINE=1` at runtime. `/api/health` also checks the model is loaded.
- `retrieval/embedder.py` (batches of `EMBED_BATCH_SIZE`); the ingestion pipeline embeds the chunk text and stores the vector.
- `retrieval/search.py`: cosine search, similarity ≥ `SIMILARITY_CUTOFF`, capped, keep top `TOP_N` by cosine for now. Nothing above the cutoff → "not found in your documents" without calling the model.
- `llm/client.py` (timeout, retries) and `llm/prompts.py` (answer prompt: context only, end each statement with `[cXX]` ids).
- `retrieval/citations.py`: map `[c12]` to document, pages, heading path; drop unknown ids.
- `POST /api/chat` returning **plain JSON** `{answer, sources}` for now (SSE comes in milestone 10). Question and recent history come from the client.
- Basic Chat page: message list, input, answer with the source tags rendered from `sources`, "New chat", empty state linking to Upload, errors shown as a message.
- `scripts/smoke_test.sh`: fresh clone → `docker compose up --build` → wait for health → upload a sample PDF → ask one question → check the answer has a valid source.
- Tests: citation mapping, "not found" path (with fake embedder and fake LLM).

**Out of scope:** enrichment, rerank, rewrite, selection, streaming.

**Check:**
- Upload a real PDF, ask 5 questions you know the answers to. The answers are right and the source tags point to the right pages.
- Ask 2 questions not in the PDF: you get "not found" or a clearly hedged answer.
- Print or log the cosine scores for these questions and check `SIMILARITY_CUTOFF` 0.45 is sensible. Record what you saw in `docs/decisions.md`.
- `scripts/smoke_test.sh` passes from a fresh clone in a new folder.

---

## 7. Enrichment (`m7-enrichment`)

**Goal:** every chunk gets a context sentence, a summary and keywords from Haiku, and the context improves the embedding.

**Read:** `design/retrieval-approach.md` A6-A7; `design/tech-stack.md` (Chat LLMs: prompt caching, batching, large documents).

**Build:**
- `ingestion/enricher.py`: one Haiku call per section with the document (prompt-cached) and all its chunks, JSON back per chunk. `ENRICH_CONCURRENCY` sections in parallel, `ENRICH_BATCH_SIZE` chunks per call for long sections. Invalid JSON → one retry → store unenriched (`enriched = false`). Documents over Haiku's context window send the section instead of the whole document.
- Embed context sentence + chunk text.
- Update `chunks_done` as sections finish (drives the progress bar later).
- Tests: valid JSON stored; invalid JSON twice → chunks stored unenriched, document still `ready`.

**Out of scope:** retrieval changes.

**Check:** upload a PDF; in the DB most chunks have `enriched = true` with sensible summaries; the fallback test shows a failed enrichment still ends with the document `ready` and its chunks `enriched = false`. Note the upload time for a real PDF in `docs/decisions.md`.

---

## 8. Rerank and "not found" (`m8-rerank-not-found`)

**Goal:** a cross-encoder reorders the candidates, and weak matches give "not found".

**Read:** `design/retrieval-approach.md` B2-B4; `design/tech-stack.md` (Reranker).

**Build:**
- bge-reranker-v2-m3 downloaded at build time (pinned), `retrieval/reranker.py`.
- `retrieval/pipeline.py` started here: search (up to `MAX_CANDIDATES`) → rerank → top `TOP_N`. Reranker failure → keep cosine order.
- "Not found" when nothing passes the cutoff or the best rerank score is below `RERANK_MIN_SCORE` (pick a provisional default from your test questions; the evaluation tunes it).
- The pipeline returns a **trace**: chunk ids after each stage (needed by the evaluation).
- Tests: reranker failure falls back; low rerank score gives "not found" without the answer call.

**Out of scope:** rewrite, selection.

**Check:** re-ask the milestone 6 questions; answers are at least as good. The unanswerable ones now say "not found". Check `docker stats` shows the `api` container within your 8 GB.

---

## 9. Follow-up rewrite and section selection (`m9-rewrite-and-selection`)

**Goal:** follow-up questions work, and answers that span several chunks of a section get the missing chunks.

**Read:** `design/retrieval-approach.md` B0, B5-B7; `design/testing-evaluation.md` §1 (Combine step, Fallbacks rows).

**Build:**
- `retrieval/rewriter.py` (B0): Haiku turns a follow-up plus `HISTORY_TURNS` of history into a standalone question; failure → raw question.
- `retrieval/selector.py` (B6): one Sonnet call with the question and the summaries + keywords of every chunk in the kept sections; returns extra chunk ids; failure → top N only.
- Combine (B7): top N + selected, each chunk once, in document order, labelled with id, heading path and page.
- Trace extended with the rewrite and the selection stage.
- Tests: combine order and de-duplication; each fallback.

**Out of scope:** streaming, UI changes.

**Check:** ask a question, then "and what about X?" style follow-up: the answer understands the context. Ask a question whose answer spans a whole section: the answer is complete. The fallback tests pass, so a failing rewrite or selection still gives an answer.

---

## 10. Streaming chat (`m10-streaming-chat`)

**Goal:** the answer streams in, with the source tags appearing inline as it streams.

**Read:** `design/app-structure.md` §3 (`/api/chat`); `design/frontend-pages.md` §2.

**Build:**
- `/api/chat` as SSE: `sources` event (id → document, pages, heading path), then text events, then `done`; an `error` event on failure.
- `api/client.ts` SSE reader with `fetch`; `CitationChip` replaces `[c12]` as text arrives; several ids in one bracket.
- Clicking a tag opens `/api/documents/{id}/file#page=N` in a new tab.
- Check nginx really streams (no buffering).

**Out of scope:** citation highlighting inside the PDF.

**Check:** in the browser, the answer appears word by word through nginx on port 8080 (not all at once), tags appear inline, clicking one opens the PDF at the right page. `scripts/smoke_test.sh` updated and passing.

---

## 11. Upload polish (`m11-upload-polish`)

**Goal:** duplicates, overwrites, progress and errors are handled properly.

**Read:** `design/retrieval-approach.md` A2; `design/app-structure.md` §4 (overwrite bullet); `design/frontend-pages.md` §1.

**Build:**
- `overwrite=true`: ingest the new version first, then delete the old one in one transaction; a failed overwrite keeps the old document.
- `DuplicateDialog`: "This document is already uploaded. Overwrite it?" with Overwrite / Cancel.
- Progress bar from `chunks_done / chunk_count`.
- Clear error text for encrypted, no text, too large, interrupted.
- Tests: overwrite replaces chunks; failed overwrite keeps the old ones.

**Check:** upload the same PDF twice → dialog → Overwrite → still one document, new chunks; Cancel → nothing changes. Restart `api` mid-upload → document shows "interrupted, please re-upload".

---

## 12. Database page (`m12-database-page`)

**Goal:** a read-only view of what ingestion produced.

**Read:** `design/frontend-pages.md` §3; `design/app-structure.md` §3 (sections and chunks endpoints).

**Build:**
- `GET /api/documents/{id}/sections` and `GET /api/sections/{id}/chunks` (+ tests).
- `DatabasePage`: documents table → `SectionTree` → `ChunkTable` (text, context, summary, keywords, pages, "not enriched" marker, embedding present yes/no). No delete here.

**Check:** click through a real PDF from document to sections to chunks; the numbers match the Upload page.

---

## 13. README and docs (`m13-readme`)

**Goal:** a reviewer can run the app from the README alone, and understands what was built and why.

**Read:** `design/app-structure.md` §7, §8; `docs/decisions.md`; `design/testing-evaluation.md` §3.

**Build:**
- `README.md`: how to run (copy `.env.template`, add the key, `docker compose up --build`, open `localhost:8080`, **8 GB Docker memory**, the 4-5 GB model download during the build), what was built, decisions and why (from `docs/decisions.md`, each with the rejected option), what was left out on purpose, next steps (answer evaluation first, then keyword/BM25 hybrid search, OCR, neighbours vs. selection, server-side history, task queue, migrations).
- `docs/architecture.md`: the diagram and the two pipelines.
- Bring `docs/decisions.md` up to date, including "What broke".

**Check:** follow the README word for word in a fresh clone in a new folder (ideally with Docker's cache cleared: `docker builder prune`). `scripts/smoke_test.sh` passes. Someone who has never seen the project could run it.

---

## 14. Evaluation (`m14-evaluation`, extra)

Only start once milestones 1-13 are merged and the happy path is stable. Split into two branches if it gets big (harness first, then questions and tuning).

**Goal:** retrieval numbers for the README: hit rate on the answerable questions and refusal rate on the unanswerable ones (updated 2026-10-04, see `docs/decisions.md`).

**Read:** `design/testing-evaluation.md` §2; `design/evaluation-metrics.md` (all).

**Build:**
- `eval/` as a compose profile (`docker compose --profile eval run --rm eval python run.py`), own database `docchat_eval` created from code.
- Question YAML files (5 PDFs × 24 questions, standalone, about 20 unanswerable; gold headings picked from the parser's section tree); you spot-check 10 per PDF.
- `run.py` calls the same retrieval function as `/api/chat` and records the trace; `report.py` computes the rates with Wilson intervals and the leave-one-PDF-out tuning of `SIMILARITY_CUTOFF`, `RERANK_MIN_SCORE`, `TOP_N`.
- `eval/results.md` committed and linked from the README; set the tuned defaults in `env/config.py`.

**Check:** `eval/results.md` has the headline table; the README says clearly that answers are not evaluated yet and that this is the next step.

Other optional extra after this: citation highlighting inside the PDF.

---

## Before the demo

- Clean-clone smoke test one last time.
- Ingest the bigger demo PDF beforehand; keep a small one for the live upload.
- Have `eval/results.md` and `docs/decisions.md` open.
