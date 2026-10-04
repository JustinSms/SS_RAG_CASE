# Architecture

How the app is put together and how the two pipelines work. The reasons behind each choice are in [decisions.md](decisions.md); the full design is in [design/](design/).

## Containers

```
 Browser
   │
   ▼
 ┌──────────────┐   /api/*    ┌──────────────────────────────┐        ┌───────────────────┐
 │ web (nginx)  │ ──────────▶ │ api (FastAPI, Python)        │ ─────▶ │ db (Postgres +    │
 │ React SPA    │             │  • ingestion pipeline        │        │     pgvector)     │
 └──────────────┘             │  • retrieval pipeline        │        └───────────────────┘
                              │  • bge-m3 + reranker (local) │
                              │  • Anthropic client          │ ─────▶  Anthropic API
                              └──────────────────────────────┘          (Haiku, Sonnet)
                                         │
                                         ▼
                                 uploads volume (original files)
```

- **web** serves the React app and proxies `/api` to the api. It is the only published port (8080). Upload size (10 MB) and SSE streaming (`proxy_buffering off` for `/api/chat`) are set in nginx.
- **api** holds all logic: parsing, chunking, enrichment, embedding, search, reranking, prompting and answering. The embedding and reranker models run inside it on the CPU; they are downloaded when the image is built.
- **db** is Postgres with pgvector. It holds documents, sections, chunks and the vectors. Tables are created when the api starts.
- The only secret is `ANTHROPIC_API_KEY`. Every threshold and model name is a setting in `env/config.py`.
- The chat history lives in the browser and is sent with each question; the server stores no conversations.

## Ingestion pipeline (upload)

Code: `backend/app/ingestion/`. One document is processed at a time by a worker thread; the upload request returns `202` straight away and the page polls the document list.

| Step | What happens | If it fails |
|---|---|---|
| Checks | PDF header, size, readable, not encrypted, has text. Same hash as an existing document → `409` and the Overwrite dialog | The upload is rejected with a clear message |
| Parse | PyMuPDF4LLM turns the PDF into markdown per page, with headings | Document is marked `failed` |
| Sections | Headings become a section tree (parent, level, heading path, pages). No headings → pseudo-sections of `MAX_CHUNK_SIZE` | |
| Chunk | Each section is split on paragraph boundaries into chunks of at most `MAX_CHUNK_SIZE` tokens, with `CHUNK_OVERLAP_TOKENS` overlap. A chunk never crosses a section | |
| Enrich | One Haiku call per section (the document is prompt-cached) returns a context sentence, a summary and keywords per chunk | After one retry the chunks are stored with `enriched = false` and embedded as plain text. Never fails a document |
| Embed | bge-m3 embeds context + text in batches of `EMBED_BATCH_SIZE` | Document is marked `failed` |
| Store | Chunks, vectors, summaries and keywords are saved; the document becomes `ready` | |

An overwrite stores the new version under a temporary hash, runs this pipeline, and only then swaps it in with the old one deleted in one transaction. A failed overwrite keeps the old document. If the api restarts while a document is `processing`, it is marked `failed` ("interrupted, please re-upload").

## Question pipeline (chat)

Code: `backend/app/retrieval/`. `select_context` runs steps 0-7 and returns the ordered context plus a trace of chunk ids per stage; the answer is then streamed.

| Step | What happens | If it fails |
|---|---|---|
| 0 Rewrite | With history, Haiku turns a follow-up into a standalone question | The raw question is used |
| 1 Embed | bge-m3 embeds the question | |
| 2 Search | Cosine search over `ready` documents: closest `MAX_CANDIDATES`, then everything above `SIMILARITY_CUTOFF` | |
| 3 Rerank | bge-reranker-v2-m3 scores the candidates (0-1) | Cosine order is kept |
| 4 Keep | Top `TOP_N`. Nothing above the cutoff, or best rerank score below `RERANK_MIN_SCORE` → "not found in your documents", and the answer model is not called | |
| 5 Group | The sections the kept chunks belong to | |
| 6 Select | One Sonnet call sees the chunk summaries of those sections and picks up to `MAX_SELECTED` extra chunks | Only the top N are used |
| 7 Combine | Top N plus selected chunks, each once, in document order, labelled `c1`, `c2`, ... with heading path and pages | |
| 8 Answer | Sonnet answers from that context only and puts the labels it used at the end of the sentence or short paragraph they support | This is the only required call; a failure arrives as an `error` event in the stream |

`/api/chat` answers with Server-Sent Events: a `sources` event (label → document, pages, headings), then `text` pieces, then `done` (or `error`). The browser replaces each `[c3]` with a source tag that opens the PDF at the cited page, and draws nothing for labels that are not in `sources`.

## Data model

```
documents ──< sections (parent_id → sections) ──< chunks (embedding vector(1024), HNSW index)
```

Deleting a document cascades to its sections and chunks. Details are in [design/app-structure.md](design/app-structure.md) §4.
