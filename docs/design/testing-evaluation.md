# Document Chat: Testing and Evaluation

Status: agreed, updated 2026-10-04. Builds on `retrieval-approach.md`, `tech-stack.md`, `app-structure.md`, `frontend-pages.md`.
Principle: two separate layers. **Tests** prove the code does what it says (fast, no API key). **Evaluation** measures how good retrieval is: whether a right source is in the context, and whether unanswerable questions are refused (needs the key, produces numbers for the README). The generated answers are not evaluated yet; that is the next step (see `docs/decisions.md`).

## 1. Tests (pytest, run on every commit)

Deterministic, no network, LLM and models replaced by small fakes.

| What | Example checks |
|---|---|
| `sections.py` | Headings become the right tree; heading path `2 Scope > 2.1 Data`; text before the first heading lands in a root section |
| `chunker.py` | Chunks never exceed `MAX_CHUNK_SIZE`, keep the overlap, never cross a section; page ranges correct when a chunk spans a page break; a PDF without headings becomes pseudo-sections |
| Combine step (B7) | Top N + selected chunks: each chunk once, in document order, labelled with heading path and pages |
| Citation mapping | `[c12]` maps to document, pages, headings from the DB; unknown ids are dropped; a statement without an id is detected |
| Fallbacks | Failing rewrite, reranker or selection still gives an answer; invalid enrichment JSON stores the chunk unenriched |
| Startup | Missing API key reported by `/api/health`; documents left in `processing` are marked failed |
| "Not found" | Nothing above `SIMILARITY_CUTOFF` or best rerank below `RERANK_MIN_SCORE` gives the "not found" answer without calling the answer model |
| API (FastAPI `TestClient`) | Upload returns `202`; same file again returns `409`; over 10 MB `413`; non-PDF `415`; `overwrite=true` replaces chunks, and a failed overwrite keeps the old ones; delete cascades; `/api/health` |

Plus one **Docker smoke test** script: fresh clone, `docker compose up --build`, wait for health, upload a sample PDF, ask one question, check an answer with a valid citation comes back. This is the test for "it runs on our machine". Run it after every build step from step 3, and before the demo.

Not planned: frontend unit tests and end-to-end browser tests (the smoke test covers the happy path; "exhaustive edge cases" are explicitly not evaluated).

## 2. Evaluation (`eval/`, run on demand)

The details (hit rule, question file, rates, noise, cross-validation, schema) are in `evaluation-metrics.md`. Summary:

### Setup
- **5 public PDFs, 24 questions each, 120 in total** (2 already downloaded). Suggested: EU AI Act in English and German (backs the multilingual model choice), a technical standard, an annual report with tables (shows where PyMuPDF4LLM struggles), and one more regulation. For the English/German pair, both language versions count as gold (see `evaluation-metrics.md` §1).
- **Gold is a heading.** Claude reads each PDF and marks the document and the deepest heading containing the answer, as a full heading path copied from the parser's section tree (`eval/trees/`). Pages are not used for matching.
- You spot-check 10 labels per PDF before the first run.

### Questions
Two kinds, all standalone (no conversation history), with no further types:

| Kind | Share | Correct when |
|---|---|---|
| Answerable | ~80% (about 100) | At least one chunk of the final context is in a gold section or a subsection of it |
| Unanswerable: plausible, on-topic, not in the documents | ~15-20% (about 20) | The system says "not found" |

Not in the set, and so not measured: follow-up questions (the rewrite step B0) and questions that need two documents. See `docs/decisions.md`.

### Metrics (on the final context that would be given to the answer model)
- **Hit rate** on the answerable questions and **refusal rate** on the unanswerable ones, reported separately, overall and per PDF. Refusal precision (how many "not found" answers were right) next to them, plus context size in tokens and chunks per section.
- **No precision, recall or per-stage table:** one right chunk makes a hit, which keeps the numbers easy to explain. Cost: the evaluation cannot show whether the context is complete, so it cannot show what section selection adds.
- **No answer grading:** answers are not generated or judged in the evaluation. Evaluating them (by hand or with an LLM) is the next step of the project.
- **Noise:** Wilson intervals on every rate (about ±8 points for the answerable questions, about ±20 for the unanswerable ones), and flip counts with a sign test when comparing two configurations.
- **Tuning:** leave-one-PDF-out cross-validation for `SIMILARITY_CUTOFF`, `RERANK_MIN_SCORE` and `TOP_N`, instead of a fixed dev/test split. The target is the number of correct questions (hits plus right refusals).

### Comparisons
- **Cutoff sweep** as part of the tuning; closes the open "check the cutoff against bge-m3" item.
- Not now (next steps): neighbours vs. LLM section selection (needs a completeness measure, which the hit rate is not). Dense vs. hybrid (dense + keyword/BM25) search, once keyword search is added, compared on the hit rate.
- Optional: with vs. without enrichment (context sentence in the embedding).

### How it runs
A separate script in `eval/`, started on demand as a compose profile (`docker compose --profile eval run --rm eval python run.py`), with its own database `docchat_eval` so the app database stays empty. The eval script creates it from code on start (`CREATE DATABASE` if missing, then `create_all`); no Postgres init script. `/api/chat` and the eval call the same retrieval function, which returns a trace of chunk ids and scores. Flow: ingest, write the questions, a scores-only run, tune, the final run, report (no manual grading; see `eval/README.md`). `eval/results.md` is committed and linked from the README.

## 3. How it fits the call
- Don't run the evaluation live (it takes minutes and costs API calls for selection). Show `eval/results.md` instead.
- One table tells the retrieval story: hit rate and refusal rate on the final context, with the intervals, and the thresholds chosen from the tuning. Say clearly that the answers themselves, follow-ups and two-document questions are not evaluated yet.
- Pick 2–3 questions from the set for the live demo, including one unanswerable one, so the demo matches the numbers.
- Expect questions such as "how did you pick 0.45?": the tuning table is the answer. "How do you know reranking helps?" can be answered by a run with a different setting and `report.py compare`; the per-stage table was cut.

## 4. Build order
Tests grow with build steps 2–4 in `app-structure.md`. The retrieval trace goes in with the retrieval pipeline (step 4). The questions can be written any time before that and also guide the choice of test documents. `run.py` and `report.py` come after the happy path works (step 7). Next project step after that: evaluate the answers (by hand or with an LLM judge).

## Decided
- 5 public PDFs, 120 questions, gold headings marked by Claude from the parser's section tree.
- Hit = at least one retrieved chunk in a gold section. Hit rate (answerable) and refusal rate (unanswerable) on the final context, reported separately. No precision, recall, question types or per-stage table (2026-10-04).
- **No grading of answers in this evaluation.** Source overlap is the quick win; evaluating the answers is the next step (recorded in `docs/decisions.md`).
- Follow-up and two-document questions left out (2026-10-04).
- Cross-validation (leave-one-PDF-out) for tuning. Separate `eval/` script with its own database.

## Former open questions (all settled)
1. Answer correctness: not evaluated now; by hand or with an LLM judge is decided in the next step.
2. Neighbours vs. selection comparison: decided, out of scope, listed under next steps.
3. Diagnostic table: cut (2026-10-04).
4. Final choice of the 5 PDFs: Justin picks them once the app runs, so they can be chosen against real results.
