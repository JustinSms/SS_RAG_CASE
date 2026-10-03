# Retrieval evaluation

Measures how well the retrieval finds the right passages: **accuracy, precision and recall on source overlap**. It runs the same retrieval function as `/api/chat` (steps B0-B7) and never calls the answer model. **The generated answers are not evaluated yet**; that is the next step (see `docs/decisions.md`). The metrics are defined in `docs/design/evaluation-metrics.md`.

It runs in its own database (`docchat_eval`, created by the scripts) so the app database stays empty and the chat never searches these PDFs. `docker compose up` does not start it.

## What you provide

1. **PDFs** in `eval/pdfs/` (public documents, each under 10 MB).
2. **Questions**, one YAML file per PDF in `eval/questions/`, about 24 per PDF:

   ```yaml
   - id: ai-act-07
     document: eu-ai-act-en.pdf          # file name in eval/pdfs
     question: "Which AI practices are prohibited?"
     type: single_fact                   # single_fact | multi_chunk | cross_document | follow_up | unanswerable
     answerable: true
     gold:                               # empty for unanswerable
       - {document: eu-ai-act-en.pdf, heading: "CHAPTER II > Article 5"}
     history: []                         # follow_up: the earlier turns, [{role: user, content: "..."}, ...]
   ```

   `heading` is a **full heading path exactly as it appears in the heading tree** (`eval/trees/<pdf>.txt`, one path per line, written by `ingest.py`). Pick the deepest heading that contains the answer. A chunk counts as a hit if its section is the gold section or a subsection of it. If the same content exists in two languages, list the matching heading of both PDFs as gold.

## Run it

Needs `env/.env` with your key and about 8 GB of Docker memory for the models. Stop the app first (`docker compose down`) so two copies of the models do not share the memory.

```
docker compose --profile eval run --rm eval python ingest.py        # PDFs -> database, writes eval/trees/
# now write the questions, picking gold headings from eval/trees/
docker compose --profile eval run --rm eval python run.py --label sweep --scores-only
docker compose --profile eval run --rm eval python report.py tune   # leave-one-PDF-out thresholds -> eval/folds.json
docker compose --profile eval run --rm eval python run.py --label final --folds folds.json
docker compose --profile eval run --rm eval python report.py report # writes eval/results.md
```

- `ingest.py` goes through the real ingestion (parse, sections, chunks, Haiku enrichment, embedding), so it calls Anthropic once per section. It skips a PDF that is already ingested.
- `run.py --scores-only` runs at the loosest settings of the grid and skips the selection call. It stores the cosine and rerank score of every candidate, so `report.py` can recompute any threshold without more calls.
- `run.py --folds` runs the full retrieval; each question uses the thresholds tuned on the *other* PDFs. This is the headline run.
- `run.py` stops with a warning if an optional step (rewrite, rerank, selection) fell back during a question: those numbers would not show the real pipeline. A reranker that cannot load stops the run.
- Editing a question or a gold heading means running `run.py` again (all runs that should be compared).
- `report.py compare --a run1 --b run2` prints how many questions only one of two runs gets right and the sign-test p-value.

Gold headings that are not in the heading tree are rejected at the start of `run.py`, with the question id.

## Files

```
pdfs/        the PDFs
questions/   one YAML per PDF
trees/       heading tree per PDF, written by ingest.py (gold headings are picked from these)
ingest.py    PDFs -> database through the real ingestion, exports trees/
run.py       retrieval per question, stores the trace per stage
report.py    metrics, intervals, tuning, flips; writes results.md and folds.json
metrics.py   the maths (overlap, accuracy, precision, recall, Wilson, sign test, tuning); no database
questions.py loads and checks the question files
db.py        creates docchat_eval and its tables (schema eval: questions, gold, results)
results.md   committed result, linked from the README
```
