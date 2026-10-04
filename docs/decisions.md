# Decisions

The main architecture decisions, what I rejected and why. The README has a one-line summary of each; this file gives the reasoning.

## 1. Own frontend and backend, built from scratch

**Decision.** A React frontend and a FastAPI backend, both written for this project. Libraries (PDF parser, vector database, UI components) are used, but no ready-made chat product or RAG framework.

**Rejected.** Forking a chat product (not allowed by the brief), Streamlit or Gradio (no real frontend/backend split), and reusing an older RAG codebase I had from another project. That code was built for German procurement law, had bugs (for example, deleting a file also deleted other files with the same name) and stored no page numbers, so it could not support citations. I took ideas from it, not code.

## 2. Two Claude models with different jobs

**Decision.** Claude **Haiku** does the many small jobs: summarising every chunk at upload and rewriting follow-up questions. Claude **Sonnet** does the two jobs where quality matters: choosing related chunks and writing the answer.

**Why.** An upload can need dozens of calls, so they should be fast and cheap. The answer is what the user reads, so it gets the stronger model.

## 3. Local models for search, so the reviewer needs only one key

**Decision.** The embedding model (bge-m3) and the reranker (bge-reranker-v2-m3) run inside the Docker container. They are downloaded when the image is built, so the app works offline apart from the Claude calls.

**Rejected.** Hosted embeddings and reranking (Voyage, OpenAI, Cohere). They would mean a smaller image, less memory and faster uploads.

**Why.** The most likely reason a reviewer's run fails is a missing or wrong key, so only one key (Anthropic) is needed. Local models also cost nothing per question and have no rate limits. I also currently have no access to a cloud platform, so for this case local models were the simplest option. **Accepted cost:** a larger image, 8 GB of Docker memory and slower uploads on a laptop CPU.

**In production** I would use hosted models from AWS or Azure instead: no models in the image, less memory, faster uploads, and one cloud account for everything.

**Known limit.** A question only reliably finds passages written in its own language, so an English question about a German PDF can be refused as "not found". The evaluation has no cross-language questions, so this is not measured. The planned fix is one cheap Haiku call that translates the question into the language of the stored documents before the search.

## 4. Chunks follow the document's structure

**Decision.** The PDF's headings become a section tree. Each section is split at paragraph boundaries into chunks of at most about two pages, with a small overlap. A chunk never crosses into another section, and it remembers its heading path and pages.

**Rejected.** Fixed-size chunks across the whole text (they cut topics in half and lose the heading), and one chunk per heading, which was the problem in my old code: closely related subsections ended up as separate scraps.

**Why.** Every answer can cite chapter and page, and the section tree makes it possible to bring in related chunks later (decision 6).

## 5. Every chunk gets a context sentence, a summary and keywords

**Decision.** At upload, Haiku writes for every chunk a sentence saying where it sits in the document, a short summary and a few keywords. The context sentence is embedded together with the chunk text. This follows Anthropic's "contextual retrieval" technique.

**Rejected.** One call per chunk (too slow) and Anthropic's batch API (half the price, but it runs asynchronously and results can take minutes to hours, which breaks a live upload). Instead there is one call per section, and the document is cached so it is paid for only once.

**Why.** A chunk that says "the limit is 3 hours" is hard to find on its own. With "This chunk describes battery duration for emergency lighting" in front of it, the search finds it. The summaries are also what the selection step reads.

## 6. Retrieval: wide net, reranker, then an LLM picks related chunks

**Decision.** For each question:
1. A loose similarity search collects up to 20 candidates.
2. A reranker scores each candidate against the question and keeps the best 5. If even the best one is weak, the app says "not found".
3. Claude Sonnet sees the summaries of all other chunks **in the same sections** as those 5 and adds the ones needed for a complete answer.

**Rejected: a ready-made "auto-merging" or "parent document" retriever** (LlamaIndex's AutoMergingRetriever, LangChain's ParentDocumentRetriever). These treat the document as a tree: once a set share of a section has been found (for example 50%), the found pieces are replaced by the whole section, and this repeats one level up until a token budget (for example 2,000 tokens) is used up. I rejected it for three reasons:
- It depends on two fixed numbers, the share and the budget, which have no natural value and must be tuned.
- When the budget is too small, a whole section is dropped or cut, and the rules have no way to tell which part matters.
- Scoring bigger blocks does not help either: a whole section almost always scores worse against a precise question than its best chunk.

The LLM selection avoids the fixed numbers. The merge rules count how much of a section was found, not whether the missing part matters, and a token budget cuts by size, not by meaning. The LLM instead reads the summaries and judges "is this chunk needed for *this* question?", which is what the rules were trying to imitate. Limiting it to the sections the top 5 came from keeps the call small (a section of 10 chunks is roughly 300 tokens of summaries).

**Also rejected.** Trusting the similarity score alone (scores are bunched together and only mean "same topic"), and running the LLM before the reranker (it would have to read 15-20 sections, most of them noise).

**Accepted cost.** One extra Sonnet call per question, and the choice is based on summaries, so a detail missing from a summary can be missed. A simple "add the neighbouring chunks" rule is the comparison I would run next.

## 7. Postgres with pgvector as the database

**Decision.** One Postgres database, with the pgvector extension, in its own container.

**Rejected.** Chroma, LanceDB and Qdrant.

**Why.** The data is relational: documents contain sections, sections contain chunks. Postgres stores those links and the vectors together, and its built-in full-text search makes keyword search a cheap next step.

## 8. Every optional step falls back

**Decision.** Rewriting the question, reranking, chunk selection and enrichment are optional. If one fails, the app continues with a simpler version (the raw question, the similarity order, the top 5 only, unenriched chunks). Only the final answer call is required.

**Why.** The demo must work even if Anthropic is slow or a model does not load. The answer gets a bit less precise instead of failing.

## 9. Deliberately simple where scale does not matter

**Decision.** One document is processed at a time, chat history lives in the browser, and the database tables are created at startup.

**Rejected.** A task queue with Redis, server-side chat history and database migrations.

**Why.** This is a single-user demo. Each of these would add containers or code that the demo never uses. They are listed as next steps.

## 10. Evaluate retrieval first, answers later

**Decision.** The evaluation measures only whether the search finds the right section (and says "not found" when it should). It does not grade the answers. 120 questions over 5 public PDFs; thresholds are tuned on four PDFs and tested on the fifth, in turn.

**Rejected for now.** Grading all answers by hand (slow) or with an LLM judge (needs to be checked against hand grades before it can be trusted).

**Why.** It is fast, cheap and repeatable, and it tests the part of the system I control most directly.

**Tuning result.** The tuning picked a similarity cutoff of 0.3 (range tried 0.3 to 0.6) and a rerank minimum of 0.5 (range tried 0.01 to 0.5), with 5 chunks kept (3, 5 or 8 tried). Both thresholds sit at the edge of the range, with the score still rising there, so the real best values probably lie beyond it. They are not applied yet: the app still uses 0.45 and 0.1.

**What it does not tell us.** Whether the answers are correct. A model can still misread the right passage. **Grading the answers is the most important next step.**

## What broke along the way

- **Formatting tags in headings.** The PDF parser marks coloured or underlined text with HTML tags, which then showed up in headings, citations and prompts. The parser now strips them.
- **The evaluation ran on an outdated image.** The first evaluation used an older setting (50 search candidates instead of 20) because the evaluation image had not been rebuilt. I kept the results and documented the caveat instead of spending more hours on a rerun.
- **Two PDFs in one upload were rejected.** The web server limits the size of the whole request, so two 6 MB files failed although each was under 10 MB. The browser now sends one file per request.
- **The "not found" check is weak.** The evaluation showed that the reranker rates on-topic passages highly even when they do not answer the question, so only 6 of 20 unanswerable questions were refused. This is the main open issue.
- **The evaluation stops before the answer.** It was designed to measure retrieval only, so it ends at the reranker. For 14 of the 20 unanswerable questions the search passes 5 chunks to the answer model, and the evaluation never sees what the model does with them: whether it declines or makes something up. The real refusal rate therefore lies anywhere between 30% (6 of 20) and 100%. Since the retrieval guard turned out to be weak, the answer model is the actual last line of defence, and it is exactly the step that is not measured. Grading the answers, starting with these 14 cases, is the first next step.
- **Cross-language questions were noticed too late.** The design assumed that the multilingual models (bge-m3 and bge-reranker-v2-m3) would handle an English question about a German document. An early test already showed the opposite: an English question against a German passage got a rerank score of 0.013, far below the cutoff, so the app answers "not found". The evaluation was meant to test this with an English/German pair, but the chosen PDFs had none, so the problem was never measured and only became clear in manual use at the end. The fix (translating the question into each document language before the search) is a next step, not built.
