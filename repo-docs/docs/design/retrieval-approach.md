# Document Chat: Retrieval Approach

Status: agreed design, updated 2026-10-03. Models and tools are in `tech-stack.md`; every variable is listed in `app-structure.md` §6.

## A. When a document is uploaded

1. **Checks:** PDF only (file header checked), at most `MAX_UPLOAD_MB` (10 MB). Encrypted PDFs and PDFs without text are rejected with a clear message.
2. **Duplicate check:** hash the file. If the same hash already exists, ask the user: *"This document is already uploaded. Overwrite it?"* If they say yes, ingest the new version and then delete the old one in one transaction, so a failed overwrite keeps the old document. If they say no, stop. Never skip silently.
3. **Parse:** convert the file to text with PyMuPDF4LLM, keeping page numbers and headings.
4. **Build sections:** build the section tree from the headings (chapter → sub-chapter), so each section knows its parent and its heading path. A PDF without headings is split into pseudo-sections of `MAX_CHUNK_SIZE`.
5. **Chunk:** split each section on paragraph boundaries into chunks of at most `MAX_CHUNK_SIZE` tokens (default 1,200, about two pages), with `CHUNK_OVERLAP_TOKENS` overlap. A chunk never crosses a section. Each chunk stores its section, its position within the section, its page(s) and its heading path.
6. **Enrich (one Haiku call per section):** the call gets the document (prompt-cached) and all chunks of the section, and returns JSON with, per chunk:
   - 1–2 sentence context (where the chunk sits in the document)
   - 1–3 sentence summary
   - a few keywords

   Up to `ENRICH_CONCURRENCY` sections run in parallel; long sections are sent in groups of `ENRICH_BATCH_SIZE` chunks. If the JSON is invalid after one retry, the chunks are stored without enrichment and embedded as plain text. Enrichment never fails a document.
7. **Embed:** the context sentence plus the chunk text, with bge-m3, in batches of `EMBED_BATCH_SIZE`.
8. **Store:** the chunk, its embedding, summary, keywords and section links.

One document is processed at a time. If the app restarts mid-upload, the document is marked failed ("interrupted, please re-upload").

## B. When a question is asked

0. **Rewrite follow-ups:** with recent chat history, Haiku turns a follow-up into a standalone question. If this fails, the raw question is used.
1. **Embed the question.**
2. **Cosine search:** fetch every chunk with similarity ≥ `SIMILARITY_CUTOFF`, capped at `MAX_CANDIDATES`.
3. **Rerank:** score those chunks against the question with the reranker. If reranking fails, keep cosine order.
4. **Keep the top `TOP_N`.** If nothing passed the cutoff, or the best rerank score is below `RERANK_MIN_SCORE`, answer *"not found in your documents"* without calling the answer model.
5. **Group by section:** the unique sections the kept chunks belong to.
6. **LLM selection (one Sonnet call):** the question plus, for each section, the summaries and keywords of all its chunks. The LLM returns the IDs of the extra chunks needed to answer. If this fails, continue with the top N only.
7. **Combine:** the top N plus the selected chunks, each chunk once, in document order, labelled with an id (`c12`), heading path and page.
8. **Answer:** Sonnet answers from that context only and ends each statement with the ids it used (`[c12]`). The backend maps the ids to document, pages and headings; unknown ids are dropped.

Only step 8 is required for an answer; steps 0, 3 and 6 fall back as described.

## Key variables

| Variable | Default | Purpose |
|---|---|---|
| `SIMILARITY_CUTOFF` | 0.45 | Minimum cosine similarity. Low on purpose: bge-m3 scores for relevant passages often sit around 0.5-0.7, so this only removes clear noise and the reranker does the real filtering. Check on a real PDF at build step 3, tune in the evaluation |
| `MAX_CANDIDATES` | 50 | Cap on chunks sent to the reranker |
| `TOP_N` | 5 | Chunks kept after reranking |
| `RERANK_MIN_SCORE` | set during tuning | Below this → "not found" |
| `MAX_CHUNK_SIZE` | 1200 tokens | Hard cap on a chunk (about two pages) |

Full list: `app-structure.md` §6.
