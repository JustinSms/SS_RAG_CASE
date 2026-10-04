# Document Chat

Upload PDFs and ask questions about them. Answers come only from your documents and cite their sources: each sentence or short paragraph ends with a tag like `[Contract.pdf, p. 12-13, 3.1 Scope]` that opens the PDF at that page. If the documents do not contain the answer, the app says so instead of guessing.

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

**If something is wrong**, a banner at the top of the page says what (missing or invalid API key, low memory, models not loaded, api unreachable). After fixing `env/.env`, run `docker compose up -d api` (this recreates the container, so it reads the new `env/.env`; `restart` would keep the old values); the banner clears by itself.

### Using it

- **Upload:** drop PDFs (max 10 MB each, text PDFs only; each file is sent in its own request). The list shows a progress bar while a document is processed; larger documents take a minute or more on a CPU. Uploading the same file again asks whether to overwrite it.
- **Chat:** ask a question. Follow-ups such as "and what about the second one?" work. Conversations live in the browser: "New chat" starts a new one, and the History panel on the right (on screens at least 1024px wide) keeps the last 10.
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

Every threshold, limit and model name is a setting in [env/config.py](env/config.py). All prompts are in `backend/app/llm/prompts.py`, and all Anthropic calls go through `backend/app/llm/client.py` (timeout and retries). Base images, Python and npm dependencies and the two local models (by commit) are pinned. The Claude models are set by name; `claude-haiku-4-5` is an alias of a dated snapshot.

## Retrieval evaluation

Measures whether the retrieval finds a right source: the **hit rate** on answerable questions (at least one chunk of the context is in a gold section) and the **refusal rate** on unanswerable ones (the system says "not found"), reported separately. It runs the same retrieval function as `/api/chat` (steps B1-B7) and never calls the answer model, so **the generated answers are not evaluated**. The metrics are defined in [docs/design/evaluation-metrics.md](docs/design/evaluation-metrics.md).

It runs as the compose service `eval` (profile `eval`, so `docker compose up` does not start it) in its own database, `docchat_eval`, created by the scripts. The app database stays empty and the chat never searches these PDFs.

**PDFs.** Five public PDFs, not in the repository (`*.pdf` is gitignored): `A-EW_290_Windthesen_WEB.pdf`, `GenAIInUnternehmen.pdf` (German), `NIST.CSWP.29.pdf`, `PolarBearHandbookforArcticGuides2026.pdf` and `cfpb_your-home-loan-toolkit.pdf` (English). Put them in `eval/pdfs/` under these names.

**Questions.** One YAML file per PDF in `eval/questions/`: 24 per PDF, 4 of them unanswerable, 120 in total. Every question is standalone (no conversation history):

```yaml
- id: cfpb-01                                      # unique across all files
  document: cfpb_your-home-loan-toolkit.pdf        # file name in eval/pdfs
  question: "What is force-placed insurance, and how much more can it cost me?"
  answerable: true
  gold:
    - {document: cfpb_your-home-loan-toolkit.pdf, heading: "Choosing the best mortgage for you > Be sure to budget for homeowner's insurance"}
  # evidence: p. 4, "the cost to you could be twice as much as you would regularly pay for insurance"

- id: cfpb-21
  document: cfpb_your-home-loan-toolkit.pdf
  question: "What is the maximum loan amount for an FHA loan in 2026?"
  answerable: false
  gold: []                                         # empty for unanswerable
```

`heading` is a **full heading path exactly as it appears in the heading tree** (`eval/trees/<pdf file name>.txt`, for example `eval/trees/NIST.CSWP.29.pdf.txt`, one path per line, written by `ingest.py`). Pick the deepest heading that contains the answer. A question is a hit if at least one chunk of the context is in a gold section or a subsection of it. If the same content exists in two languages, list the matching heading of both PDFs as gold; finding either is a hit. The `# evidence` and `# why not answerable` comments are notes for the person checking the question; the loader ignores them.

These five fields are the only ones allowed. `run.py` stops and lists every problem at once if a field is missing or unknown, `answerable` is not `true`/`false`, an answerable question has no gold (or an unanswerable one has gold), an id is used twice, or a gold heading is not in the heading tree.

**Run it.** `ingest.py` needs `env/.env` with your key for the Haiku enrichment. It does not check the key: without one it still runs, and the chunks are stored unenriched (the log shows the failed calls). The scores-only run and the report need no key; the full run checks it and stops without one. Give Docker about 8 GB of memory and stop the app first (`docker compose down`) so two copies of the models do not share the memory.

```
docker compose --profile eval run --rm eval python ingest.py        # PDFs -> database, writes eval/trees/
docker compose --profile eval run --rm eval python run.py --label sweep --scores-only
docker compose --profile eval run --rm eval python report.py tune   # leave-one-PDF-out thresholds -> eval/folds.json
docker compose --profile eval run --rm eval python report.py report # scores the sweep with those thresholds -> eval/results.md
```

Optional, a full run with section selection (needs the key; one Sonnet call per question, roughly doubles the time):

```
docker compose --profile eval run --rm eval python run.py --label final --folds folds.json
docker compose --profile eval run --rm eval python report.py report --final final
```

- `ingest.py` goes through the real ingestion (parse, sections, chunks, Haiku enrichment, embedding), so it calls Anthropic once per section. It skips a PDF that is already ingested.
- `run.py --scores-only` runs at the loosest settings of the grid and skips the selection call. It stores the cosine and rerank score of every candidate, so `report.py` can recompute any threshold without more calls. The tuning counts the correct questions (hits plus right refusals) for every setting of the grid, and picks, per parameter, the middle of the settings within `EVAL_TUNE_TOLERANCE` (1% of the questions) of the best.
- `report.py report` recomputes the top N after reranking from the stored scores, using for each PDF the thresholds tuned on the *other* PDFs. That is the headline. It does not need a second run: section selection only adds chunks from sections the top N already hit, so it cannot change a hit or a refusal.
- `run.py --folds` is the optional full run. It adds the real size of the context with the selected chunks and the selection latency; the hit and refusal rates stay the same.
- `run.py` stops with a warning if an optional step (rerank, selection) fell back during a question: those numbers would not show the real pipeline. A reranker that cannot load stops the run.
- Both scripts print a progress line per item, with the elapsed time and an estimate of the time left:

  ```
  [2/5] GenAIInUnternehmen.pdf: 214 sections, 612 chunks in 4:10 | elapsed 7:30 | left ~11:15
  [ 37/120] cfpb-01  hit              2.1s | elapsed 1:18 | left ~2:55 | hits 31/33 | refused 3/4
  ```

  `hits` and `refused` are running totals (answerable questions with a hit, unanswerable questions refused). In the `--scores-only` run they are at the loosest settings without selection, so they are not the final numbers. A line ending in `| FALLBACK: an optional step failed` means the run will fail at the end: stop it and check the log. To follow a run from another terminal, start it with `run -d` and use `docker logs -f <container>`.
- Editing a question or a gold heading means running `run.py` again (all runs that should be compared).
- `report.py compare --a run1 --b run2` prints how many questions only one of two runs gets right and the sign-test p-value. It needs `folds.json` (from `report.py tune`). By default (`--stage rerank`) it rescores both runs' stored candidates with those thresholds, so it shows differences in the candidates (for example another embedding text or chunking), not in thresholds. To compare runs made with different thresholds, use `--stage final`, which scores each run's stored context. There is no switch to run without the reranker.

Not measured: follow-up questions (the rewrite step), questions that need two documents, and whether the context is complete (one right chunk is a hit). See [docs/decisions.md](docs/decisions.md).

### Results (first run, 2026-10-04)

**In short:** whenever the documents can answer a question, the right passage was among the 5 chunks the search picked. When the documents cannot answer, the search only said "not found" for 6 of 20 questions.

| | What was checked | Result |
|---|---|---|
| 100 questions the documents answer | Is the right section among the top 5 chunks? | **100 of 100** (between 96% and 100%) |
| 20 questions the documents do not answer | Did the search say "not found"? | **6 of 20** (between 15% and 52%) |
| The 6 "not found" answers | Were they for unanswerable questions? | 6 of 6: no real question was refused |

By PDF, every PDF found the right passage for all 20 answerable questions. "Not found" for the 4 unanswerable ones: Windthesen 0, GenAI 2, NIST 0, Polar bears 1, CFPB 3.

**What this means**
- **Finding the right passage works well.** Even with only 3 chunks (`TOP_N` 3) 99 of 100 questions were still found.
- **Saying "not found" works poorly.** For 14 of the 20 unanswerable questions the search still hands 5 chunks to the answer model. The reranker judges how related a passage is to the topic, not whether it answers the question, and the unanswerable questions are on-topic on purpose. What the answer model then does with those chunks (decline or make something up) is not measured, because answers are not evaluated yet.
- **Thresholds.** The tuning chose `SIMILARITY_CUTOFF` 0.3, `RERANK_MIN_SCORE` 0.5 and `TOP_N` 5 for every PDF. The first two are the edge of the range that was tried (0.3 to 0.6 and 0.01 to 0.5) and the score was still rising there, so the best value is probably a higher `RERANK_MIN_SCORE`. They are **not applied yet**: the app still uses 0.45, 0.1 and 5.
- **Speed.** About 78 seconds per question on average (95% under 112 seconds), with the reranker on the CPU in Docker.

**How much to trust it**
- **The run used 50 candidates per question** (`MAX_CANDIDATES`), because the eval image was older than the change to 20 that the app uses now. It was decided not to rerun for this. With 20 candidates the numbers can differ a little and the search is faster.
- **100% is probably too flattering.** The sections are small (about 1 chunk each) and the questions were written with the answer text in view, so this test cannot tell a good setting from a mediocre one.
- **20 unanswerable questions is a small sample**, hence the wide range of 15% to 52%.
- The failures list in `eval/results.md` still shows HTML tags (`<mark>`, `<sup>`) in headings, from the parser before it was changed.

All tables, the tuning grid and every failed question: [eval/results.md](eval/results.md).

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
| Chat history in the browser (`localStorage`), sent with each question | Server-side conversations | No conversation tables or endpoints |
| Safe overwrite: ingest the new version, then swap in one transaction | Delete first, then ingest | A failed overwrite keeps the old document |
| Tables created at startup (`create_all`) | Alembic migrations | One schema version so far |
| Unit tests on in-memory SQLite with small fakes for models and Anthropic | Tests that need the `db` container, network or models | `pytest` runs on any laptop without Docker or a key. The pgvector search is checked by the smoke test |

## What was left out on purpose

- **OCR.** A scanned PDF is accepted, then marked failed with "no text found" while it is processed.
- **Keyword search.** Search is dense (vectors) only.
- **Server-side chat history and accounts.** One user, history in the browser.
- **Migrations.** The schema is created at startup.
- **Other file types.** PDF only, 10 MB max.
- **Header and footer filtering.** A running page header that PyMuPDF4LLM reads as a heading can become a section (seen on a test paper).
- **Final thresholds.** The first evaluation run is done (see [Results](#results-first-run-2026-10-04)), but the thresholds it picked are at the edge of the range that was tried, so they are not applied: `SIMILARITY_CUTOFF` (0.45) and `RERANK_MIN_SCORE` (0.1) stay provisional. In a quick check, an English question against a German passage scored low enough to be refused at 0.1; the question set has no cross-language questions, so it does not measure this.
- **Answer quality is not measured.** Only retrieval is (see [Retrieval evaluation](#retrieval-evaluation)); whether answers are correct is not evaluated yet.

## Known issues

- **A failing embedding model shows no banner.** bge-m3 is loaded at startup without a fallback; if that fails, the api does not start, so `web` never starts either. Check `docker compose logs api`.
- **A question of only spaces is not rejected.** It runs the pipeline with an empty question.
- **`ingest.py` (eval) does not check the API key.** Without a key the eval PDFs are stored unenriched without a clear warning.
- **Test packages in the api image.** The tests are not copied in, but `uv sync` installs the dev group (pytest, httpx).
- **Documents ingested before the parser removed styling tags** keep `<mark>`, `<u>` and `<sup>` in their headings and chunks until they are uploaded again. The eval data keeps them on purpose: its gold headings carry the same tags, so the results stay consistent (see `docs/decisions.md`).

## Next steps

1. **Evaluate the answers** (by hand or with an LLM judge), together with citation validity.
2. **Finish the retrieval tuning.** The first run chose thresholds at the edge of the tried range. Widen the `RERANK_MIN_SCORE` grid (for example up to 0.9), rerun with the current `MAX_CANDIDATES` and set the tuned cutoff and rerank threshold as defaults.
3. **Keyword (BM25) hybrid search** with Postgres full-text search, compared against dense-only in the evaluation.
4. **OCR** for pages without a text layer (for example Tesseract through PyMuPDF).
5. **Neighbour chunks vs. LLM section selection**, compared on context completeness, context size and cost (needs a completeness measure; the hit rate cannot show it).
6. **Server-side chat history.**
7. **A task queue** (Celery/RQ + Redis) for several users and parallel uploads.
8. **Migrations** with Alembic.

## Repository

```
docker-compose.yml
env/            config.py (all settings) and .env.template
backend/        FastAPI app (app/), tests, Dockerfile, uv.lock
frontend/       React app (src/), nginx.conf, Dockerfile
eval/           retrieval evaluation (see below)
scripts/        smoke_test.sh (clean-clone check)
docs/           architecture.md, decisions.md, implementation-plan.md, design/
LICENSE
```

`eval/` holds:

```
pdfs/        the PDFs (not in the repository, see above)
questions/   one YAML per PDF
trees/       heading tree per PDF, written by ingest.py (gold headings are picked from these)
ingest.py    PDFs -> database through the real ingestion, exports trees/
run.py       retrieval per question, stores the trace per stage
report.py    metrics, intervals, tuning, flips; writes results.md and folds.json
progress.py  elapsed time and time left for the progress lines
metrics.py   the maths (hit rule, hit and refusal rates, Wilson, sign test, tuning); no database
questions.py loads and checks the question files
db.py        creates docchat_eval and its tables (schema eval: questions, gold, results)
folds.json   thresholds per PDF, written by report.py tune
results.md   the result, written by report.py report
```
