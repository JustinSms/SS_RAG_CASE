# Document Chat: Evaluation Metrics in Detail

Status: agreed, updated 2026-10-04 (simplified: hit rate and refusal rate only, see `docs/decisions.md`). Expands section 2 of `testing-evaluation.md`.
Setup: 5 public PDFs, 24 questions each, 120 in total (about 100 answerable, about 20 unanswerable). All 120 are used for both tuning and scoring through leave-one-PDF-out cross-validation (section 5). Rates are computed per PDF and overall.

**Scope decision:** this evaluation measures only whether the retrieval finds **a right source**: for an answerable question, whether at least one chunk of the context is in a gold section; for an unanswerable question, whether the system says "not found". The generated answers are **not** graded. Evaluating the answers (by hand or with an LLM) is the next step of the project, see `docs/decisions.md`.

## 1. Ground rules

- **Gold is a heading, not a chunk id or a page.** For every answerable question, Claude reads the PDF and records the document and the deepest heading that contains the answer. Gold survives re-chunking and re-ingestion.
- **Gold headings are full heading paths from the parser's section tree.** `ingest.py` exports the heading paths the ingestion produced for each PDF (`eval/trees/<pdf>.txt`, one path per line, for example `CHAPTER II > Article 5`), and the gold is copied from there. Otherwise a correct retrieval can count as a miss because Claude and PyMuPDF4LLM name a heading differently. Cost: a parser mistake (a missed heading) does not show up as a retrieval failure. Covered by a one-time look at each PDF's heading tree.
- **Deepest heading.** If the answer is in "3.2.1", the gold is "3 > 3.2 > 3.2.1", not "3". A coarse gold makes almost every chunk a hit.
- **Hit rule.** A retrieved chunk has a source `[document, page(s), heading path]`. It is **in a gold section** if its section is the gold section or a subsection of it, in the same document. A chunk in a parent section's own text does not count unless the parent is the gold. Pages are shown to the user and are not used for matching. **One such chunk makes the question a hit**, however many other chunks the context holds, and however many gold sections the question has.
- **Same content in two languages.** The app always searches all documents, so an English question about the EU AI Act may correctly retrieve the German copy. For questions on that pair, the matching heading in both language versions is listed as gold; finding either one is a hit.
- **The score is taken on the final context.** All numbers are computed on the chunks that would be given to the answer model (step B7). The answer model is not called in the evaluation.

## 2. Questions

### Question file
Questions live in YAML files in the repo (versioned, reviewable), one file per PDF, and are loaded into the `eval` database schema (section 6). Every question is standalone (no conversation history):

```yaml
- id: ai-act-07                  # unique across all files; prefix it with the PDF
  document: eu-ai-act-en.pdf     # the PDF the question belongs to (decides its fold, section 5)
  question: "Which AI practices are prohibited?"
  answerable: true
  gold:                          # one or more sections that contain the answer
    - {document: eu-ai-act-en.pdf, heading: "CHAPTER II > Article 5"}
    - {document: eu-ai-act-de.pdf, heading: "KAPITEL II > Artikel 5"}   # the German copy, if there is one

- id: ai-act-21
  document: eu-ai-act-en.pdf
  question: "What is the budget of the EU AI Office for 2027?"
  answerable: false
  gold: []                       # empty for unanswerable
```

There is no question type and no reference answer: answers are not evaluated yet. A `reference_answer` field can be added when they are.

### Checks before a run
`run.py` loads the files first and stops, listing every problem at once, if:
- a field is missing (`id`, `document`, `question`, `answerable`) or unknown (a typo, or `type` / `history` from the old format);
- `answerable` is not `true` or `false`;
- an answerable question has no gold, or an unanswerable one has gold; a gold entry lacks its document or heading;
- two questions share an id (across all files);
- a gold `(document, heading)` is not in the ingested section trees (a typo, a shortened path, or a PDF the parser saw differently).

### Building the set
- Claude drafts about 40 candidate questions per PDF from the PDF and the heading list; you keep 24, rewrite them in your own words, and check the gold.
- Avoid questions that copy a heading verbatim, since they flatter retrieval.
- About 4 of the 24 per PDF (about 20 in total) are unanswerable: plausible, on-topic, but not in the document. The "not found" threshold needs enough of these.
- **Spot-check before the first run:** open 10 random questions per PDF (50 in total) and confirm the gold heading really contains the answer and exists in the tree. If the same kind of error appears twice, fix the rule, not just the question.

### Not in the set
- **Follow-up questions.** Without a history the follow-up rewrite (B0) never runs, so the numbers say nothing about it.
- **Questions that need two documents.** Under the hit rule they would count as a hit when either document is found, so they would add little.

Both are recorded in `docs/decisions.md` as not measured.

## 3. Metrics

The system "refuses" when it would answer "not found" (nothing above `SIMILARITY_CUTOFF`, or best rerank score below `RERANK_MIN_SCORE`). Answerable and unanswerable questions are **reported separately**, because they measure different things: finding the right passage, and knowing when to say no.

- **Hit rate** (answerable questions) = share of answerable questions where at least one chunk of the final context is in a gold section. A refused answerable question is a miss.
- **Refusal rate** (unanswerable questions) = share of unanswerable questions the system refuses. Low means the thresholds are too loose (the answer model would get unrelated context and may make something up).
- **Refusal precision** = right refusals / all refusals. Low means the thresholds are too strict (answerable questions are refused).
- **Context size** in tokens (mean over the questions that were answered), and the **average chunks per section** of each PDF. Large sections make hits easier, so the second number belongs next to the hit rate.
- **Latency** of the retrieval pipeline (mean and p95).

Every rate is printed with its counts and a 95% interval, for example `85/100 (77–91%)`.

**What a hit does not tell you.** It means one right chunk was in the context, not that the context was complete. Section selection (B6), which brings in the rest of a section, cannot raise the hit rate once the top N already hit. Precision, recall and a per-stage table (cosine, rerank, final) were dropped to keep the numbers easy to read and explain; see `docs/decisions.md`.

## 4. Not evaluated yet: the answers

Whether the generated answer is correct, complete and faithful to the sources is **not** measured here. Finding a right source is necessary for a good answer but not sufficient (the model can still misread or ignore the context). Evaluating the answers, by hand (correct / partial / wrong against a reference answer) or with an LLM judge, together with citation validity and precision, is the next step of the project. See `docs/decisions.md`.

## 5. Noise, tuning and comparisons

### Sampling noise
The questions are a sample, so every rate is an estimate. The 95% interval is about ±1.96 × √(p(1−p)/n):

| Rate | n=100 (answerable) | n=20 (unanswerable) |
|---|---|---|
| 90% | ±6 points | ±13 points |
| 80% | ±8 points | ±18 points |
| 50% | ±10 points | ±22 points |

- The script uses the Wilson interval and prints rates as `85/100 (77–91%)`.
- Questions from the same PDF resemble each other, so the effective sample is a bit smaller. Report the spread across the 5 PDFs, and read a single PDF's row as an indication of where retrieval fails.
- The refusal rate rests on about 20 questions: read it as a rough guard, not a precise number.
- Retrieval is deterministic (same questions and settings give the same chunks). The section selection call is an LLM call (temperature: see the open point in `docs/decisions.md`).

### Comparing two configurations
Run both on the same questions and count the flips: questions only A gets right (b) and only B gets right (c), answerable and unanswerable together. A sign test on b against c says whether the difference is real (12 against 3: p ≈ 0.04; 8 against 5: p ≈ 0.58). Rule of thumb: about 15 flipped questions in a ratio of about 3 to 1. `report.py compare` prints `A only: b, B only: c, p`.

### Tuning with leave-one-PDF-out
Instead of a fixed dev/test split, tune on 4 PDFs and score the 5th, repeated for every PDF. The pooled scores of the 5 held-out folds cover all 120 questions and are the honest estimate. It also shows whether the thresholds hold on an unseen document.
- Tuned: `SIMILARITY_CUTOFF`, `RERANK_MIN_SCORE`, `TOP_N`, over the grids `EVAL_CUTOFF_GRID`, `EVAL_RERANK_GRID`, `EVAL_TOP_N_GRID` in `env/config.py`.
- **Target:** the number of correct questions, hits on the answerable ones plus refusals of the unanswerable ones. The tuning needs one number; the report still shows the two rates separately.
- Settings within `EVAL_TUNE_TOLERANCE` (1% of the questions) of the best count as equally good; the pick is the middle of them per parameter, not the single best value.
- The tuning scores the **rerank stage** (top N, no section selection): it is recomputed from stored scores, while selection is an LLM call. Section selection only adds chunks, so it cannot turn a hit into a miss; it does not change refusals either.
- The cross-validated numbers are what the README reports as expected performance. The pooled pick over all questions is the default for `env/config.py`.
- Does not shrink the interval above. It uses all questions for both tuning and scoring without scoring a question that picked its own threshold.

## 6. How the evaluation fits into the project

- **Separate script, same code path.** `eval/` lives in the repo, is not needed for the happy path, and is started on demand. The retrieval pipeline returns a trace (chunk ids plus scores); `/api/chat` and the eval call the same function, so the eval measures the real code. This is the only change to app code.
- **Runs in Docker** as a fourth compose service under a profile, using the `api` image with `eval/` mounted: `docker compose --profile eval run --rm eval python run.py`. `docker compose up` does not start it. It reuses the models, `env/config.py` and the Anthropic key (for enrichment during ingestion and the selection step; no answer calls).
- **Own database.** `docchat_eval` in the same Postgres container, created by the eval script on start (`CREATE DATABASE` if missing, then `create_all`), so the app database stays empty and the chat never searches the eval PDFs. Tables in the `eval` schema: `questions`, `gold` (question, document name, heading path as text, no foreign key to `sections`, so re-ingestion doesn't break it), `results` (run, question, stage `candidates` or `final`, chunks with their scores, refused, latency, fallback).
- **Fallbacks stop the run.** If the reranker cannot load, or the rerank or selection step falls back during a question, `run.py` exits non-zero and lists the questions: the numbers would describe a different pipeline.
- **Thresholds** come from `env/config.py`; the tuning overrides them per run.

```
eval/
  pdfs/          the 5 public PDFs (or a download list if the licence is unclear)
  questions/     one YAML per PDF
  trees/         heading paths per PDF, written by ingest.py (gold is copied from here)
  ingest.py      loads the PDFs through the real ingestion pipeline, writes trees/
  run.py         runs retrieval per question (steps B1-B7), stores the candidates and the final context
  report.py      rates, intervals, tuning, flip counts; writes folds.json and results.md
  metrics.py     the maths, no database
  questions.py   loads and checks the question files
  README.md      how to run it
```

Flow: `ingest.py`, write the questions, `run.py --scores-only` (loosest settings, no selection call), `report.py tune` (leave-one-PDF-out thresholds into `folds.json`), `run.py --folds folds.json` (the full pipeline with each PDF's thresholds), `report.py report` (writes `results.md`). No manual grading step. Commit `results.md` and link it from the README so reviewers see the numbers without running anything.

## 7. Reporting (`results.md`)

Counts next to every percentage:
1. **Main table** (final context, cross-validated), overall and per PDF: hit rate (answerable), refusal rate (unanswerable), context tokens, chunks per section. Refusal precision below it, and the retrieval latency.
2. **Tuning**: correct questions over the grid of `SIMILARITY_CUTOFF` and `RERANK_MIN_SCORE`, hit and refusal rate per `TOP_N`, the pooled pick and the pick per held-out PDF.
3. **Failures**: every missed question with its retrieved chunks and the gold section (or "refusal"), to explain in the call.
4. **How much to trust the numbers**: the noise paragraph above in two sentences, what a hit does not tell you, what is not measured (follow-ups, two-document questions), and that the answers themselves are not evaluated yet.

## Open points
1. Which PDFs? Justin picks them once the app is running. 2 are already downloaded. Suggestion for 5: EU AI Act (English), the same act in German, a technical standard, an annual report with tables, and one more regulation. Pick files under 10 MB (the upload limit). The effort is the labelling: about 100 gold headings, so Claude's draft plus your spot-check keeps it manageable.
