# Document Chat: Evaluation Metrics in Detail

Status: agreed, updated 2026-10-03. Expands section 2 of `testing-evaluation.md`.
Setup: 5 public PDFs, 24 questions each, 120 in total. All 120 are used for both tuning and scoring through leave-one-PDF-out cross-validation (section 5). Metrics are computed per PDF and overall.

**Scope decision:** this evaluation measures only the **overlap between the retrieved sources and the gold sources**, as accuracy, precision and recall. The generated answers are **not** graded. Evaluating the answers (by hand or with an LLM) is the next step of the project, see `docs/decisions.md`.

## 1. Ground rules

- **Gold is a heading, not a chunk id or a page.** For every answerable question, Claude reads the PDF and records the document and the deepest heading that contains the answer. Gold survives re-chunking and re-ingestion.
- **Gold headings are chosen from the parser's section tree.** Claude gets the heading list that the ingestion pipeline produced for the PDF (exported as text) and picks from it. Otherwise a correct retrieval can count as a miss because Claude and PyMuPDF4LLM name a heading differently. Cost: a parser mistake (a missed heading) does not show up as a retrieval failure. Covered by a one-time look at each PDF's heading tree.
- **Deepest heading.** If the answer is in "3.2.1", the gold is "3.2.1", not "Chapter 3". A coarse gold makes almost every chunk a hit.
- **Overlap rule.** A retrieved chunk has a source `[document, page(s), heading(s)]`. It **overlaps the gold** if its section is the gold section or a subsection of it, in the same document. A chunk in a parent section's own text does not count unless the parent is the gold. Pages are shown to the user and are not used for matching.
- **Same content in two languages.** The app always searches all documents, so an English question about the EU AI Act may correctly retrieve the German copy. For questions on that pair, the matching heading in both language versions is listed as gold.
- **The headline is the final context.** All main numbers are computed on the chunks that would be given to the answer model (step B7). Earlier pipeline stages are diagnostic only (section 3). The answer model is not called in the evaluation.

## 2. Questions

### Question file
Questions live in YAML files in the repo (versioned, reviewable) and are loaded into the `eval` database schema (section 6):

```yaml
- id: ai-act-07
  document: eu-ai-act-en.pdf
  question: "Which AI practices are prohibited?"
  type: single_fact          # single_fact | multi_chunk | cross_document | follow_up | unanswerable
  answerable: true
  gold:                      # empty for unanswerable
    - {document: eu-ai-act-en.pdf, heading: "Article 5"}
  history: []                # for follow_up: the previous turns
```

There is no reference answer: answers are not evaluated yet. A `reference_answer` field can be added when they are.

### Building the set
- Claude drafts about 40 candidate questions per PDF from the PDF and the heading list; you keep 24, rewrite them in your own words, and check the gold.
- Avoid questions that copy a heading verbatim, since they flatter retrieval.
- About 4 of the 24 per PDF (about 20 in total) are unanswerable: plausible, on-topic, but not in the document. The "not found" threshold needs enough of these.
- **Spot-check before the first run:** open 10 random questions per PDF (50 in total) and confirm the gold heading really contains the answer and exists in the tree. If the same kind of error appears twice, fix the rule, not just the question.

## 3. Metrics

For one question, let **R** = the chunks in the final context and **G** = the chunks in the gold sections (including their subsections) in the database. The system "refuses" when it would answer "not found" (nothing above `SIMILARITY_CUTOFF`, or best rerank score below `RERANK_MIN_SCORE`).

- **Accuracy** = share of all questions with a correct outcome. An answerable question is correct if R overlaps the gold (at least one chunk from a gold section); an unanswerable question is correct if the system refuses. Report it overall, per PDF and per question type. For answerable questions alone this is the classic **hit rate**.
- **Recall** (answerable questions) = share of the gold sections that appear in R. Matters for multi-section questions, where one hit is only a partial success.
- **Precision** (answerable questions) = |R ∩ G| / |R|: how much of the context was relevant. With `TOP_N` 5 and few relevant chunks it has a ceiling, so read it next to recall.
- Precision and recall are averaged over questions (macro average).
- **Context size** in tokens, and the **average chunks per section** of the PDFs. Large sections make hits easier, so the second number belongs next to the accuracy.
- **Refusal precision and recall** (used for tuning `RERANK_MIN_SCORE`, computed automatically, no grading). Treat "not found" as the positive class: refusal precision = correct refusals / all refusals; refusal recall = correct refusals / all unanswerable questions (the hallucination guard). Low recall means the thresholds are too loose; low precision means too strict.
- **Latency** of the retrieval pipeline (mean and p95).

### Diagnostic table (optional, can be cut)
The pipeline trace stores the chunk ids after each step. Showing accuracy, precision and recall at these points tells you which step helps or hurts, and answers "how do you know reranking helps?":

| Stage | R is |
|---|---|
| 1. Cosine | every chunk above `SIMILARITY_CUTOFF` (capped at `MAX_CANDIDATES`) |
| 2. Rerank | the top `TOP_N` after reranking |
| 3. Final context | top N plus the chunks chosen by section selection (= the headline) |

Expected pattern, to be confirmed or contradicted: stage 1 has high recall and low precision, reranking raises precision, section selection raises recall again for multi-section questions at the cost of precision and context size. Kept for now; if presentation time is short, cut it. The headline numbers don't depend on it.

## 4. Not evaluated yet: the answers

Whether the generated answer is correct, complete and faithful to the sources is **not** measured here. Good overlap between retrieved and gold sources is necessary for a good answer but not sufficient (the model can still misread or ignore the context). Evaluating the answers, by hand (correct / partial / wrong against a reference answer) or with an LLM judge, together with citation validity and precision, is the next step of the project. See `docs/decisions.md`.

## 5. Noise, tuning and comparisons

### Sampling noise
The questions are a sample, so every score is an estimate. The 95% interval is about ±1.96 × √(p(1−p)/n):

| Score | n=120 (overall) | n=20 (one question type) |
|---|---|---|
| 90% | ±5 points | ±13 points |
| 80% | ±7 points | ±18 points |
| 50% | ±9 points | ±22 points |

- Use the Wilson interval in the script and print scores as `83/120 (75–89%)`.
- Questions from the same PDF resemble each other, so the effective sample is a bit smaller. Report the spread across the 5 PDFs.
- Per question type there are only 15–25 questions: read those rows as indications of where it fails.
- Retrieval is deterministic (same questions and settings give the same chunks). The LLM steps in the pipeline (follow-up rewrite, section selection) run at temperature 0.

### Comparing two configurations
Run both on the same questions and count the flips: questions only A gets right (b) and only B gets right (c). A sign test on b against c says whether the difference is real (12 against 3: p ≈ 0.04; 8 against 5: p ≈ 0.58). Rule of thumb: about 15 flipped questions in a ratio of about 3 to 1. The script prints `A only: b, B only: c, p` next to each comparison.

### Tuning with leave-one-PDF-out
Instead of a fixed dev/test split, tune on 4 PDFs and score the 5th, repeated for every PDF. The pooled scores of the 5 held-out folds cover all 120 questions and are the honest estimate. It also shows whether the thresholds hold on an unseen document.
- Tuned: `SIMILARITY_CUTOFF` (coarse grid, for example 0.3, 0.4, 0.5, 0.6; default 0.45), `RERANK_MIN_SCORE`, `TOP_N`. Pick the middle of a stable range, not the single best value.
- Accuracy and refusal metrics depend only on stored scores and thresholds, so the script caches the scores once and recomputes them per fold at no cost.
- The cross-validated numbers are what the README reports as expected performance.
- Does not shrink the interval above. It uses all questions for both tuning and scoring without scoring a question that picked its own threshold.

## 6. How the evaluation fits into the project

- **Separate script, same code path.** `eval/` lives in the repo, is not needed for the happy path, and is started on demand. The retrieval pipeline returns a trace (chunk ids per stage plus scores); `/api/chat` and the eval call the same function, so the eval measures the real code. This is the only change to app code.
- **Runs in Docker** as a fourth compose service under a profile, using the `api` image with `eval/` mounted: `docker compose --profile eval run --rm eval python run.py`. `docker compose up` does not start it. It reuses the models, `env/config.py` and the Anthropic key (for the rewrite and selection steps only; no answer calls).
- **Own database.** `docchat_eval` in the same Postgres container, created by the eval script on start (`CREATE DATABASE` if missing, then `create_all`), so the app database stays empty and the chat never searches the eval PDFs. Tables in the `eval` schema: `questions`, `gold` (question, document name, heading path as text, no foreign key to `sections`, so re-ingestion doesn't break it), `results` (run, question, stage, retrieved chunks, scores).
- **Thresholds** come from `env/config.py`; the sweep overrides them per run.

```
eval/
  pdfs/          the 5 public PDFs (or a download list if the licence is unclear)
  questions/     one YAML per PDF
  generate.py    optional: drafts questions from a PDF's parsed heading list
  ingest.py      loads the PDFs through the real ingestion pipeline
  run.py         runs retrieval per question (steps B0-B7), stores the trace in the DB
  report.py      metrics, intervals, flip counts, leave-one-PDF-out, results.md
  README.md      how to run it
```

Flow: `ingest`, then `run`, then `report` writes `results.md`. No manual grading step. Commit `results.md` and link it from the README so reviewers see the numbers without running anything.

## 7. Reporting (`results.md`)

Counts next to every percentage:
1. **Main table** (final context, cross-validated): accuracy, recall, precision, context size; overall and per PDF.
2. **Per question type**: accuracy, with refusal precision and recall for the unanswerable type.
3. **Tuning table**: the sweep of `SIMILARITY_CUTOFF` and `RERANK_MIN_SCORE`, which value was picked and why.
4. **Diagnostic table** (optional, can be cut): stages 1 to 3.
5. **Failures**: every missed question with its retrieved chunks and the gold section, to explain in the call.
6. **How much to trust the numbers**: the noise paragraph above, in two sentences, plus one sentence that the answers themselves are not evaluated yet.

## Open points
1. Which PDFs? Justin picks them once the app is running. 2 are already downloaded. Suggestion for 5: EU AI Act (English), the same act in German, a technical standard, an annual report with tables, and a second regulation related to the AI Act (for cross-document questions). Pick files under 10 MB (the upload limit). The effort is the labelling: 120 gold headings, so Claude's draft plus your spot-check keeps it manageable.
2. Follow-up questions need a short history; keep it as a `history:` field in the YAML.
3. Cross-document questions only make sense if two PDFs cover related topics; otherwise drop that question type.
