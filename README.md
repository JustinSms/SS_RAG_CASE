# Document Chat

Upload PDFs and ask questions about them. Answers come only from your documents and cite their sources: each statement ends with a tag like `[Contract.pdf, p. 12-13, 3.1 Scope]` that opens the PDF at that page. If the documents do not contain the answer, the app says so instead of guessing.

The frontend (React) and backend (FastAPI) are our own build. No chat product or RAG package was used, only libraries.

## Run it

You need Docker and an [Anthropic API key](https://console.anthropic.com/). Nothing else is installed on your machine.

1. **Give Docker 8 GB of memory** (Docker Desktop → Settings → Resources). The two local models need about 5 GB. The app shows a warning banner if Docker has less.
2. Copy the settings template and add your key:

   ```
   cp env/.env.template env/.env
   ```

   Open `env/.env` and set `ANTHROPIC_API_KEY=` to your key. This is the only value you have to set.
3. Start everything:

   ```
   docker compose up --build
   ```

   The first build downloads the PyTorch libraries and two models (about 4-5 GB in total), so it takes a while. Nothing is downloaded after the build.
4. Open <http://localhost:8080>. `web` starts only after the api is healthy, so the page appears once the models are loaded (this can take a minute after the build). If it shows a red banner, see below.

To stop: `Ctrl+C`, then `docker compose down`. Add `-v` to also delete the uploaded documents and the database.

**If something is wrong**, a banner at the top of the page says what (missing or invalid API key, low memory, models not loaded, api unreachable). After fixing `env/.env`, run `docker compose restart api`; the banner clears by itself.

### Using it

- **Upload:** drop PDFs (max 10 MB each, text PDFs only). The list shows a progress bar while a document is processed; larger documents take a minute or more on a CPU. Uploading the same file again asks whether to overwrite it.
- **Chat:** ask a question. Follow-ups such as "and what about the second one?" work. The conversation lives in the browser; "New chat" clears it.
- **Database:** a read-only view of what ingestion produced: documents, their section tree, and the chunks of a section with context, summary, keywords and pages.

### Tests

```
cd backend && uv run pytest        # backend: no network, no API key, no models
cd frontend && npm ci && npm test  # frontend
```

`scripts/smoke_test.sh` clones the repo into a temporary folder, builds it, uploads a sample PDF, asks a question and checks that the streamed answer carries a valid source. It needs Docker, your key (in the environment or `env/.env`) and a free port 8080.

## What was built

Three containers: `web` (nginx + React), `api` (FastAPI) and `db` (Postgres + pgvector). The diagram and both pipelines are in [docs/architecture.md](docs/architecture.md).

**When a PDF is uploaded:** it is checked, parsed with PyMuPDF4LLM, split into a section tree from its headings, and cut into chunks that never cross a section. Claude Haiku writes a context sentence, a summary and keywords for the chunks of each section. The chunks are embedded locally with bge-m3 and stored.

**When a question is asked:** a follow-up is rewritten into a standalone question; the question is embedded and compared with all chunks; a local reranker (bge-reranker-v2-m3) orders the candidates; the best few are kept, or the app answers "not found in your documents". Claude Sonnet then looks at the summaries of the sections those chunks belong to and adds extra chunks that are needed. The context goes to Sonnet in document order, and the answer streams back with source tags.

Every optional step (enrichment, rewrite, rerank, section selection) falls back to a simpler behaviour instead of failing. Only the answer call is required.

Every threshold, limit and model name is a setting in [env/config.py](env/config.py). All prompts are in `backend/app/llm/prompts.py`, and all Anthropic calls go through `backend/app/llm/client.py` (timeout and retries). Base images, Python and npm dependencies and model revisions are pinned.

## Decisions and why

The full log, with what broke along the way, is in [docs/decisions.md](docs/decisions.md). The main ones:

| Decision | Rejected | Why |
|---|---|---|
| Local bge-m3 embeddings and bge-reranker-v2-m3, in the api image | Voyage or OpenAI embeddings and reranker | One API key for the reviewer, no per-query cost, no extra outages. Costs a bigger image, 8 GB RAM and slower uploads on CPU. Both models handle German and English |
| Models downloaded at image build, pinned by commit, `HF_HUB_OFFLINE=1` at runtime | Download on first start | The app is ready right after `docker compose up --build` and behaves the same every time |
| Postgres + pgvector | Chroma, LanceDB, Qdrant | The data is relational (sections, chunks linked to sections); one store holds links and vectors, and full-text search is available later |
| FastAPI + React, SSE for streaming | Next.js API routes, Streamlit/Gradio, WebSockets | A real frontend/backend split; SSE is one-directional and works with a plain `fetch` |
| In-process queue, one document at a time | Celery/RQ + Redis | Two more containers for a single-user demo. Documents left `processing` after a restart are marked failed |
| Haiku enrichment: one call per section, document prompt-cached | One call per chunk; Message Batches API | Far fewer calls; batches are asynchronous and break a live upload |
| Question flow: low cosine cutoff (0.45), reranker does the filtering, then LLM section selection | A high cosine cutoff alone | bge-m3 scores relevant passages around 0.5-0.7, so a high cutoff drops good chunks. Section selection brings in neighbouring context the top N missed |
| Rewrite follow-ups with Haiku before retrieval | Sending the whole chat to the search | The search needs a standalone question; the answer call still gets the user's own words and the history |
| Chat history in the browser, sent with each question | Server-side conversations | No conversation tables; "New chat" is a state reset |
| Safe overwrite: ingest the new version, then swap in one transaction | Delete first, then ingest | A failed overwrite keeps the old document |
| Tables created at startup (`create_all`) | Alembic migrations | One schema version so far |
| Unit tests on in-memory SQLite with small fakes for models and Anthropic | Tests that need the `db` container, network or models | `pytest` runs on any laptop without Docker or a key. The pgvector search is checked by the smoke test |

## What was left out on purpose

- **OCR.** Scanned PDFs are rejected as "no text found".
- **Keyword search.** Search is dense (vectors) only.
- **Server-side chat history and accounts.** One user, history in the browser.
- **Migrations.** The schema is created at startup.
- **Other file types.** PDF only, 10 MB max.
- **Header and footer filtering.** A running page header that PyMuPDF4LLM reads as a heading can become a section (seen on a test paper).
- **Evaluation numbers.** Retrieval has not been measured on a question set yet, so `SIMILARITY_CUTOFF` (0.45) and `RERANK_MIN_SCORE` (0.1) are provisional. In a quick check, an English question against a German passage scored low enough to be refused at 0.1.
- **Answer quality is not measured.** Only retrieval will be (see below); whether answers are correct is not evaluated yet.

## Next steps

1. **Evaluate the answers** (by hand or with an LLM judge), together with citation validity.
2. **Retrieval evaluation** on a question set (accuracy, precision and recall on source overlap) and tuning of the cutoff, rerank threshold and `TOP_N` ([plan](docs/design/testing-evaluation.md)).
3. **Keyword (BM25) hybrid search** with Postgres full-text search, compared against dense-only in the evaluation.
4. **OCR** for pages without a text layer (for example Tesseract through PyMuPDF).
5. **Neighbour chunks vs. LLM section selection**, compared on accuracy, recall, context size and cost.
6. **Server-side chat history.**
7. **A task queue** (Celery/RQ + Redis) for several users and parallel uploads.
8. **Migrations** with Alembic.

## Repository

```
docker-compose.yml
env/            config.py (all settings) and .env.template
backend/        FastAPI app (app/), tests, Dockerfile, uv.lock
frontend/       React app (src/), nginx.conf, Dockerfile
scripts/        smoke_test.sh (clean-clone check)
docs/           architecture.md, decisions.md, implementation-plan.md, design/
```
