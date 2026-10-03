# Document Chat: Model and Tool Selection

Status: agreed, updated 2026-10-03. Belongs with `retrieval-approach.md`.

## Overview

| Component | Choice | Runs | Key needed |
|---|---|---|---|
| Summaries / context sentences, follow-up rewrite | Claude Haiku 4.5 (`claude-haiku-4-5`) | Anthropic API | Anthropic |
| LLM chunk selection + answers | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | Anthropic API | Anthropic |
| Embeddings | `BAAI/bge-m3` | Local, in Docker | none |
| Reranker | `BAAI/bge-reranker-v2-m3` | Local, in Docker | none |
| Vector store | PostgreSQL + pgvector | Docker container | none |
| Parser | PyMuPDF4LLM | Local | none |

Result: the reviewers only need **one Anthropic API key** to run the app.

## Chat LLMs

- **Haiku 4.5** creates the context sentence, summary and keywords for every chunk (upload step A6), with **one call per section** that returns JSON for all its chunks. It also rewrites follow-up questions into standalone ones (query step B0). It's fast and cheap for many small calls.
- **Sonnet 5.5** picks extra chunks from the section summaries (B6) and answers the user's question from the retrieved context (B8).
- **Prompt caching:** enrichment sends the whole document with every section call. With caching, the document is paid for once per upload instead of once per call.
- **Batching:** one call per section instead of per chunk (about 5-10x fewer calls), up to `ENRICH_CONCURRENCY` (4) in parallel. Rejected: the Anthropic Message Batches API (half the price, but asynchronous, which breaks a live upload in the demo; a "next step" for bulk ingestion).
- **Reliability:** SDK retries with backoff on 429/529/5xx and a timeout on every call.
- **Large documents:** Haiku's context window is 200K tokens. If a document is bigger, send the chunk's section instead of the whole document.

## Reranker: bge-reranker-v2-m3

- A multilingual cross-encoder (German and English).
- Runs locally, so there's no extra API key and no cost per query.
- Note: the older `bge-reranker-base` / `-large` models are English/Chinese only, so use **v2-m3**.
- Rejected: Haiku as the reranker (slower, costs per query, less consistent scores). It's a possible later comparison.

## Embeddings: bge-m3

- Multilingual (German and English) and handles long inputs (up to 8K tokens).
- Same model family as the reranker.
- Runs locally, so no extra API key.
- **`SIMILARITY_CUTOFF` defaults to 0.45**, because bge-m3 cosine scores for relevant passages often sit around 0.5-0.7. Check it on a few test questions and tune it in the evaluation.
- Encoded in batches of `EMBED_BATCH_SIZE` (32), not one chunk at a time.
- Rejected: OpenAI text-embedding-3 and Voyage (both would need an extra API key; see the trade-off below).

## Vector store: PostgreSQL + pgvector

- The design is relational (section tree, chunks linked to sections), and Postgres holds those links and the vectors in one place.
- Postgres full-text search makes keyword search (BM25-style, hybrid with the vectors) a cheap next step without another service.
- Runs as a second container (docker-compose).
- Rejected: Chroma / LanceDB (simpler Docker, but they handle the section links poorly) and Qdrant (would need a separate store for the section tree).

## Parser: PyMuPDF4LLM

- Fast and local. Outputs markdown with headings and keeps page numbers, which are needed for sections and citations.
- Licence: AGPL, which is fine for a case study.
- Fallback: Docling, if test PDFs have complex tables or layouts (better structure, but slower and heavier).
- No OCR in v1: scanned PDFs are rejected as "no text found". Next step: OCR for pages without a text layer (for example Tesseract via PyMuPDF).

## Trade-off accepted: local models instead of paid services

- The local models make the Docker image a few GB larger, the first upload is slower on CPU, and together they need about 5 GB RAM. The README states a minimum of 8 GB Docker memory, and the app warns at startup if less is available.
- Model revisions are pinned and downloaded at build time; `HF_HUB_OFFLINE=1` at runtime, so nothing downloads after the build.
- Accepted in exchange for needing only one API key (the most likely reason a reviewer's run fails is a missing key), no rate limits or outages for search, and no per-query cost.
- Rejected: Voyage embeddings + reranker (smaller image, about 1 GB RAM, faster uploads, but a second key and network calls on every upload and question).
