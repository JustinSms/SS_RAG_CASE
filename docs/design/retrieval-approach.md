# Document Chat: Retrieval Approach

Status: agreed design, updated 2026-10-04. Models and tools are in `tech-stack.md`; every variable is listed in `app-structure.md` §6.

## A. When a document is uploaded

1. **Checks:** PDF only (file header checked), at most `MAX_UPLOAD_MB` (10 MB), readable, not encrypted. A failed check rejects the upload with a clear message. Whether the PDF has text is only known after parsing (step 3): a PDF without text is accepted and then marked failed ("no text found").
2. **Duplicate check:** hash the file. If the same hash already exists, ask the user: *"This document is already uploaded. Overwrite it?"* If they say yes, ingest the new version and then delete the old one in one transaction, so a failed overwrite keeps the old document. If they say no, stop. Never skip silently.
3. **Parse:** convert the file to markdown per page with PyMuPDF4LLM, keeping page numbers and headings. The HTML tags PyMuPDF4LLM adds for styled text (`<mark>`, `<u>`, `<sup>`, `<sub>`) are removed and their text kept; `<br>` (a line break in a table cell) stays. A PDF without text fails here ("no text found").
4. **Build sections:** build the section tree from the markdown headings (chapter → sub-chapter), so each section knows its parent and its heading path. Heading text loses markdown emphasis (`*`, `_`, backticks). Text before the first heading becomes a root section "Start of document"; headings with no text of their own are kept, so the tree stays complete. A PDF without headings is split into pseudo-sections "Part 1", "Part 2", ... of about `MAX_CHUNK_SIZE` tokens.
5. **Chunk:** split each section on paragraph boundaries into chunks of at most `MAX_CHUNK_SIZE` tokens (default 1,200, about two pages). Each chunk after the first starts with the last `CHUNK_OVERLAP_TOKENS` of the previous chunk's last paragraph, so the overlap is shorter when that paragraph is short. A paragraph longer than a chunk is split first. A chunk never crosses a section. "Tokens" are an estimate, characters / `CHARS_PER_TOKEN` (4), so no tokenizer is needed. Each chunk stores its section (which holds the heading path), its position within the section and in the document, and its page(s). The sections and chunks are saved at this point, before enrichment, so the Upload page can show progress (`chunks_done / chunk_count`).
6. **Enrich (one Haiku call per section):** the call gets the document (prompt-cached) and all chunks of the section, and returns JSON with, per chunk:
   - 1–2 sentence context (where the chunk sits in the document)
   - 1–3 sentence summary
   - a few keywords

   The first section is sent alone, so its call writes the prompt cache; then the rest run up to `ENRICH_CONCURRENCY` in parallel and read the cache. Long sections are sent in groups of `ENRICH_BATCH_SIZE` chunks, one call per group. If a call fails or its JSON is invalid (not one valid entry per chunk), it is tried `ENRICH_RETRIES` (1) more time; after that the chunks of that group are stored with `enriched = false` and embedded as plain text, so a long section can end up partly enriched. If the document is above `ENRICH_DOC_MAX_TOKENS` (150K estimated tokens; Haiku's window is 200K), each call gets its section's text instead of the whole document. Enrichment never fails a document.
7. **Embed:** the context sentence plus the chunk text, with bge-m3, in batches of `EMBED_BATCH_SIZE`.
8. **Store:** during enrichment only the progress (`chunks_done`) is saved, per section. At the end the context, summary, keywords and embedding of every chunk are saved in one commit, and the document becomes `ready`.

One document is processed at a time. If the app restarts mid-upload, the document is marked failed ("interrupted, please re-upload").

## B. When a question is asked

0. **Rewrite follow-ups:** only when there is history. Haiku gets the last `HISTORY_TURNS` turns (source ids removed) and turns the question into a standalone one. If the call fails or returns nothing, the raw question is used. Steps 1-6 use the rewritten question; the answer (8) gets the user's own question and the history.
1. **Embed the question.**
2. **Cosine search:** fetch every chunk with similarity ≥ `SIMILARITY_CUTOFF`, capped at `MAX_CANDIDATES`.
3. **Rerank:** score each (question, chunk text) pair with the reranker, 0-1 (sigmoid), in batches of `RERANK_BATCH_SIZE`. The reranker sees the chunk text only, not the context sentence. If reranking fails (or the model could not be loaded at startup), keep the cosine order.
4. **Keep the top `TOP_N`.** If nothing passed the cutoff, or the best rerank score is below `RERANK_MIN_SCORE`, answer *"I could not find this in your documents."* without calling the answer model. When reranking failed there is no rerank score, so only the cutoff decides.
5. **Group by section:** the unique sections the kept chunks belong to.
6. **LLM selection (one Sonnet call, `SELECT_MODEL`):** the question plus, for each section, all its chunks, numbered 1..n, each with its pages, whether it is already kept, and its summary and keywords (a chunk without a summary shows its first `SELECT_FALLBACK_CHARS` characters). The model returns the numbers of the extra chunks needed to answer; at most `MAX_SELECTED` are added. The call is skipped when every chunk of those sections is already kept. If it fails, continue with the top N only (no retry).
7. **Combine:** the top N plus the selected chunks, each chunk once, in document order (by file name, then document, then position), labelled with an id (`c12`), file name, page(s) and heading path.
8. **Answer:** Sonnet answers from that context only and puts the ids it used at the end of the sentence or short paragraph they support (`[c12]`), once for several sentences in a row from the same chunks. The backend maps the ids to document, pages and headings in the `sources` event; ids that are not in the context are not shown (the browser hides them in the streamed answer).

Only step 8 is required for an answer; steps 0, 3 and 6 fall back as described.

## Key variables

| Variable | Default | Purpose |
|---|---|---|
| `SIMILARITY_CUTOFF` | 0.45 | Minimum cosine similarity. Low on purpose: bge-m3 scores for relevant passages often sit around 0.5-0.7, so this only removes clear noise and the reranker does the real filtering. Check on a real PDF at build step 3, tune in the evaluation |
| `MAX_CANDIDATES` | 20 | Cap on chunks sent to the reranker |
| `TOP_N` | 5 | Chunks kept after reranking |
| `RERANK_MIN_SCORE` | 0.1 | Below this → "not found". Provisional until the evaluation tunes it |
| `MAX_CHUNK_SIZE` | 1200 tokens | Hard cap on a chunk (about two pages) |

Full list: `app-structure.md` §6.
