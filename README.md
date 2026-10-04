# Document Chat

Upload PDFs and ask questions about them. The answers come only from your documents, and every statement ends with a source tag such as `[Contract.pdf, p. 12-13, 3.1 Scope]` that opens the PDF at that page. If the documents do not contain the answer, the app says so instead of guessing.

The frontend (React) and the backend (FastAPI) are my own build. No ready-made chat product or RAG framework was used, only libraries.

## 1. How to run it

You need **Docker** and an **Anthropic API key**. `ANTHROPIC_API_KEY` is the only setting you have to provide.

1. Give Docker **8 GB of memory** (Docker Desktop → Settings → Resources). The two local models need about 5 GB.
   **Windows (WSL2 backend):** Docker Desktop has no memory slider here; instead add `memory=8GB` under `[wsl2]` in `%UserProfile%\.wslconfig`, run `wsl --shutdown`, and restart Docker Desktop.
2. Add your key. The `env/` folder contains a **template**, `.env.template`. The easiest way is to rename it to `.env` (or copy it):
   ```
   mv env/.env.template env/.env
   ```
   Open `env/.env` and fill in `ANTHROPIC_API_KEY=`.
3. **First run:** build and start:
   ```
   docker compose up --build
   ```
   The first build downloads about 4-5 GB (PyTorch and two models), so **it takes a while**. Nothing is downloaded after that.

   **Every later run:** the image already exists, so this is enough:
   ```
   docker compose up
   ```
   Use `--build` again only after pulling new code.
4. Open the app:

> ### <http://localhost:8080>
>
> This is the only address you need. The page appears once the models are loaded, which can take a minute after the containers start.

To stop: `Ctrl+C`, then `docker compose down` (add `-v` to also delete the uploaded documents).

If something is wrong (missing or invalid key, too little memory), a banner at the top of the page says what. After fixing `env/.env`, run `docker compose up -d api`.

**Tests:** `cd backend && uv run pytest` and `cd frontend && npm ci && npm test`. Neither needs Docker, a network or a key. `scripts/smoke_test.sh` builds a clean copy, uploads a PDF and checks that a cited answer streams back.

## 2. What I built

The app has three pages:

- **Upload:** add PDFs (the biggest I tested had 50 pages), see a progress bar while they are processed, delete them. Uploading the same file twice asks whether to overwrite it.
- **Chat:** ask questions, including follow-ups like "and what about the second one?". Each source tag shows how confident the search was.
- **Database:** a read-only view of what the app made of each document: its section tree and its chunks with their summaries.

It runs as three containers:

```
Browser → web (React + nginx) → api (FastAPI + 2 local models) → db (Postgres + pgvector)
                                        └→ Anthropic API (Claude Haiku, Claude Sonnet)
```

**When a PDF is uploaded**

1. The PDF is checked and converted to text with its headings and page numbers.
2. The headings become a **section tree** (chapter → sub-chapter).
3. Each section is cut into **chunks** of at most about two pages. A chunk never crosses a section boundary.
4. Claude Haiku writes, for every chunk, a short **context sentence** (where it sits in the document), a **summary** and **keywords**.
5. Each chunk is turned into a vector (embedding) with a local model and stored.

**When a question is asked**

1. A follow-up question is rewritten into a standalone question (Claude Haiku).
2. The question is compared with all chunks, and the closest ones are collected.
3. A local **reranker** reads the question and each candidate together and scores how well the chunk answers it.
4. The best 5 are kept. If even the best one scores too low, the app answers "I could not find this in your documents" and stops.
5. Claude Sonnet looks at the **summaries of the other chunks in the same sections** and adds the ones needed to answer fully.
6. Claude Sonnet writes the answer from these chunks only, with a source tag after each statement. The answer streams into the chat word by word.

Every optional step (enrichment, rewrite, reranking, section selection) falls back to a simpler behaviour if it fails. Only the final answer call is required.

The full pipeline is described in [docs/architecture.md](docs/architecture.md).

## 3. Key decisions and why

The full reasoning, including what broke along the way, is in [docs/decisions.md](docs/decisions.md).

| Decision | Rejected option | Why |
|---|---|---|
| **Claude Haiku** for the many small jobs (chunk summaries, question rewrite), **Claude Sonnet** for the answer and the chunk selection | One model for everything | Haiku is fast and cheap for hundreds of calls per upload. Sonnet gives the best answer where quality matters. |
| **Local models** for embeddings (bge-m3) and reranking (bge-reranker-v2-m3) | Paid services (Voyage, OpenAI, Cohere) | I currently have no access to a cloud platform, and for this case local models were the simplest option: the reviewer needs only one API key, there is no cost per question and no extra service that can fail. The price is a bigger image, 8 GB of memory and slower uploads. In a real production system I would use a hosted model from AWS or Azure. |
| **Chunks follow the document's structure**: cut inside each section, up to about two pages | Fixed-size chunks across the whole text | A chunk keeps its heading and pages, so every answer can cite chapter and page, and related text is not split across topics. |
| **Contextual enrichment**: every chunk gets a context sentence, summary and keywords at upload | Plain chunks only | The context sentence makes a chunk findable even when its own text is vague. The summaries are what the selection step reads later. One Haiku call per section, not per chunk, keeps the cost low. |
| **Cast a wide net, then narrow down**: a loose similarity search, a reranker, then the top 5 | Trusting the similarity score alone | Similarity scores are bunched together and only say "same topic". The reranker reads question and chunk side by side and gives a much clearer score. |
| **An LLM picks the related chunks**, only from the sections the top 5 came from, based on their summaries | A ready-made "auto-merging" or "parent document" retriever (as in LlamaIndex and LangChain) that merges chunks into their whole section once a set share is found, up to a token budget | The ready-made logic depends on two fixed numbers (merge at e.g. 50%, stop at e.g. 2,000 tokens) that have no natural value: they count how much of a section was found, not whether the missing part matters. The LLM instead judges what is needed for *this* question, and limiting it to the same sections keeps the call small. |
| **Postgres + pgvector** in its own container | Chroma, LanceDB, Qdrant | The data is relational (documents → sections → chunks). One database holds those links and the vectors, and keyword search is a cheap later addition. |
| **Own FastAPI backend and React frontend**, answers streamed | Streamlit/Gradio, Next.js API routes, forking a chat product | A real frontend/backend split, which the brief asks for, and full control over the retrieval logic. |
| **Simple over scalable**: one document processed at a time, chat history in the browser, tables created at startup | Task queue with Redis, server-side chat history, database migrations | This is a single-user demo. Each of these adds containers or code that the demo does not need. |
| **Optional steps fall back instead of failing** | Failing the whole request | The app keeps working when Anthropic is slow or a model fails to load, just with less polish. |

## 4. Retrieval evaluation

**What it measures.** Whether the search finds the right passage. For each question I know which section of which PDF holds the answer. A question counts as a **hit** if at least one of the chunks the search returns comes from that section. For questions the documents cannot answer, I check whether the search correctly says **"not found"**.

**What it does not measure.** The answers themselves. Finding the right passage is necessary for a good answer, but the model can still misread it. Grading the answers is the first next step.

**Setup.** 5 public PDFs (2 German, 3 English: a wind energy paper, a GenAI study, the NIST Cybersecurity Framework, a polar bear handbook and a US home loan guide) and 120 questions: 24 per PDF, of which 4 cannot be answered from the document. The thresholds were tuned on four PDFs and tested on the fifth, in turn, so no PDF is scored with settings tuned on itself.

**Results (4 Oct 2026)**

| Question type | Result |
|---|---|
| 100 questions the documents answer | **100 of 100** found the right section in the top 5 |
| 20 questions the documents cannot answer | **6 of 20** correctly said "not found" |
| All 6 "not found" answers | were for unanswerable questions; no answerable question was wrongly refused |

**What this means**

- **Finding the right passage works well.** The app keeps the 5 best chunks per question. The evaluation also tested keeping only the best 3: then 99 of 100 questions still had the right section among them. So the result does not depend on the exact number 5.
- **Saying "not found" works poorly.** For 14 of 20 unanswerable questions, the search still passes 5 related chunks to the answer model. The reranker judges whether a passage is on topic, not whether it actually answers the question, and these questions were on topic on purpose. **Whether the answer model then declines or makes something up is not measured yet**.
- **The tuned settings are not applied yet.** The tuning picked the values below, but two of them sit at the edge of the range that was tried, with the score still rising there, so the real best values probably lie beyond it. The app therefore still runs with its original values.

| Setting | What it does | Range tried | Best value found | App uses now (adapt in config.py) |
|---|---|---|---|---|
| Similarity cutoff | Minimum similarity for a chunk to become a candidate | 0.3 to 0.6 | **0.3** (lowest value tried) | 0.35 |
| Rerank minimum | Below this reranker score the app says "not found" | 0.01 to 0.5 | **0.5** (highest value tried) | 0.3 |
| Chunks kept | How many chunks are kept after reranking | 3, 5 or 8 | 5 | 5 |

  A higher rerank minimum is the most likely way to improve the "not found" result, since it is the setting that decides when the app refuses.

**How far to trust it**

- 100% is probably too flattering: the questions were written while looking at the answer text, and the sections are small.
- 20 unanswerable questions is a small sample. The real "not found" rate could be different. 
- Follow-up questions and questions that need two documents are not part of the test.

**Run it yourself.** Put the five PDFs in `eval/pdfs/` (they are not in the repository), stop the app, then:

```
docker compose --profile eval run --rm eval python ingest.py
docker compose --profile eval run --rm eval python run.py --label sweep --scores-only
docker compose --profile eval run --rm eval python report.py tune
docker compose --profile eval run --rm eval python report.py report
```

The evaluation uses its own database, so it never mixes with your uploads. Full tables and every failed question: [eval/results.md](eval/results.md).

## 5. What I left out on purpose

- **Scanned PDFs (OCR).** A PDF without a text layer is marked as failed with "no text found".
- **Tables and images.** Tables are read as plain text; images and charts are ignored.
- **Keyword search.** Search uses vectors only, so exact codes or numbers can be missed.
- **Multilingual questions.** A question must be in the language of the documents.
- **Multiple users.** No accounts, no server-side chat history, one upload processed at a time.
- **File types other than PDF.**

## 6. What I would do next

1. **Evaluate the answers**, by hand or with an LLM judge, including whether every citation really supports its sentence.
2. **Fix the "not found" weakness**: finish the threshold tuning on a wider range and apply the result, and test whether the answer model declines correctly.
3. **Support questions in another language than the document.** Search works best within one language, so a cheap Claude Haiku call would translate the question into each document language before the search or at document upload.
4. **Add keyword search** next to the vector search and measure whether it helps.
5. **Compare the LLM chunk selection with a simple "add the neighbouring chunks" rule** on completeness, cost and speed.
6. **Add OCR** for scanned pages and better table handling.
7. **Prepare for more users**: a task queue for uploads, server-side chat history and database migrations.

## Repository

```
docker-compose.yml
env/        settings and the .env template
backend/    FastAPI app and tests
frontend/   React app and tests
eval/       retrieval evaluation (questions, scripts, results)
scripts/    smoke test
docs/       architecture, decisions, implementation plan, design notes
```
