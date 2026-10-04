# Retrieval evaluation

Measures whether the retrieval finds a right source: the **hit rate** on answerable questions (at least one chunk of the context is in a gold section) and the **refusal rate** on unanswerable ones (the system says "not found"), reported separately. It runs the same retrieval function as `/api/chat` (steps B1-B7) and never calls the answer model. **The generated answers are not evaluated yet**; that is the next step (see `docs/decisions.md`). The metrics are defined in `docs/design/evaluation-metrics.md`.

It runs in its own database (`docchat_eval`, created by the scripts) so the app database stays empty and the chat never searches these PDFs. `docker compose up` does not start it.

## What you provide

1. **PDFs** in `eval/pdfs/` (public documents, each under 10 MB).
2. **Questions**, one YAML file per PDF in `eval/questions/`, about 24 per PDF, about 4 of them unanswerable. Every question is standalone (no conversation history):

   ```yaml
   - id: ai-act-07                       # unique across all files
     document: eu-ai-act-en.pdf          # file name in eval/pdfs
     question: "Which AI practices are prohibited?"
     answerable: true
     gold:
       - {document: eu-ai-act-en.pdf, heading: "CHAPTER II > Article 5"}

   - id: ai-act-21
     document: eu-ai-act-en.pdf
     question: "What is the budget of the EU AI Office for 2027?"
     answerable: false
     gold: []                            # empty for unanswerable
   ```

   `heading` is a **full heading path exactly as it appears in the heading tree** (`eval/trees/<pdf>.txt`, one path per line, written by `ingest.py`). Pick the deepest heading that contains the answer. A question is a hit if at least one chunk of the context is in a gold section or a subsection of it. If the same content exists in two languages, list the matching heading of both PDFs as gold; finding either is a hit.

   These five fields are the only ones allowed. `run.py` stops and lists every problem at once if a field is missing or unknown, `answerable` is not `true`/`false`, an answerable question has no gold (or an unanswerable one has gold), an id is used twice, or a gold heading is not in the heading tree.

## Run it

Needs `env/.env` with your key and about 8 GB of Docker memory for the models. Stop the app first (`docker compose down`) so two copies of the models do not share the memory.

```
docker compose --profile eval run --rm eval python ingest.py        # PDFs -> database, writes eval/trees/
# now write the questions, picking gold headings from eval/trees/
docker compose --profile eval run --rm eval python run.py --label sweep --scores-only
docker compose --profile eval run --rm eval python report.py tune   # leave-one-PDF-out thresholds -> eval/folds.json
docker compose --profile eval run --rm eval python report.py report # scores the sweep with those thresholds -> eval/results.md
```

Optional, a full run with section selection (one Sonnet call per question, roughly doubles the time):

```
docker compose --profile eval run --rm eval python run.py --label final --folds folds.json
docker compose --profile eval run --rm eval python report.py report --final final
```

- `ingest.py` goes through the real ingestion (parse, sections, chunks, Haiku enrichment, embedding), so it calls Anthropic once per section. It skips a PDF that is already ingested.
- `run.py --scores-only` runs at the loosest settings of the grid and skips the selection call. It stores the cosine and rerank score of every candidate, so `report.py` can recompute any threshold without more calls. The tuning picks the thresholds with the most correct questions (hits plus right refusals).
- `report.py report` recomputes the top N after reranking from the stored scores, using for each PDF the thresholds tuned on the *other* PDFs. That is the headline. It does not need a second run: section selection only adds chunks from sections the top N already hit, so it cannot change a hit or a refusal.
- `run.py --folds` is the optional full run. It adds the real size of the context with the selected chunks and the selection latency; the hit and refusal rates stay the same.
- `run.py` stops with a warning if an optional step (rerank, selection) fell back during a question: those numbers would not show the real pipeline. A reranker that cannot load stops the run.
- Both scripts print a progress line per item, with the elapsed time and an estimate of the time left:

  ```
  [2/5] eu-ai-act-de.pdf: 214 sections, 612 chunks in 4:10 | elapsed 7:30 | left ~11:15
  [ 37/120] ai-act-07  hit              2.1s | elapsed 1:18 | left ~2:55 | hits 31/33 | refused 3/4
  ```

  `hits` and `refused` are running totals (answerable questions with a hit, unanswerable questions refused). In the `--scores-only` run they are at the loosest settings without selection, so they are not the final numbers. A line ending in `FALLBACK` means the run will fail at the end: stop it and check the log. To follow a run from another terminal, start it with `run -d` and use `docker logs -f <container>`.
- Editing a question or a gold heading means running `run.py` again (all runs that should be compared).
- `report.py compare --a run1 --b run2` prints how many questions only one of two runs gets right and the sign-test p-value.

Not measured: follow-up questions (the rewrite step), questions that need two documents, and whether the context is complete (one right chunk is a hit). See `docs/decisions.md`.

## Files

```
pdfs/        the PDFs
questions/   one YAML per PDF
trees/       heading tree per PDF, written by ingest.py (gold headings are picked from these)
ingest.py    PDFs -> database through the real ingestion, exports trees/
run.py       retrieval per question, stores the trace per stage
report.py    metrics, intervals, tuning, flips; writes results.md and folds.json
progress.py  elapsed time and time left for the progress lines
metrics.py   the maths (hit rule, hit and refusal rates, Wilson, sign test, tuning); no database
questions.py loads and checks the question files
db.py        creates docchat_eval and its tables (schema eval: questions, gold, results)
results.md   committed result, linked from the README
```
