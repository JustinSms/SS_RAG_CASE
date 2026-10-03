# Document Chat

A web app where a user uploads PDFs and asks questions about them. Answers are grounded in the documents and cite their sources. Built for a case study: the frontend and backend must be our own build, and the app must start from Docker on a reviewer's machine with only `ANTHROPIC_API_KEY` set.

## Where things are decided

- `docs/implementation-plan.md`: the milestones. **Work on one milestone at a time** and stay inside its scope.
- `docs/design/`: the agreed design. Treat it as the source of truth.
  - `app-structure.md`: containers, API, data model, backend layout, config variables, repo layout.
  - `retrieval-approach.md`: the ingestion steps A1-A8 and the question steps B0-B8.
  - `tech-stack.md`: models and tools, and why.
  - `frontend-pages.md` + `globals.css`: pages, components and theme.
  - `testing-evaluation.md` + `evaluation-metrics.md`: tests and the retrieval evaluation.
- `docs/decisions.md`: running decision log (choice, rejected option, why) and "What broke".

If the design and the code need to differ, stop and ask before changing direction. Then record the change in `docs/decisions.md`.

## Rules

- Stack: FastAPI (Python) backend, React + TypeScript + Vite + Tailwind v4 + shadcn/ui frontend, Postgres + pgvector. Three containers: `web`, `api`, `db`.
- Do not fork or drop in a finished chat product or a pre-assembled chat + RAG package (LibreChat, Open WebUI, AnythingLLM and similar). Libraries are fine.
- Every threshold, limit and model name is a variable in `env/config.py` (pydantic-settings). No magic numbers in the code.
- All LLM prompts live in `backend/app/llm/prompts.py`. All Anthropic calls go through `backend/app/llm/client.py` (timeout and retries).
- Optional pipeline steps (enrichment, follow-up rewrite, rerank, section selection) must fall back instead of failing. Only the answer call is required.
- Pin every version: base images, Python dependencies (lockfile), `package-lock.json`, model revisions.
- Tests run without network, without an API key and without the real models (use small fakes). `pytest` must pass before every commit.
- Keep code simple and readable. Each pipeline file reads top to bottom like the steps in `retrieval-approach.md`.
- Never commit `env/.env`, API keys, the case brief HTML, or uploaded PDFs.
- Small commits with clear messages. Never squash or rewrite history.
- When you make a choice the design doesn't cover, or something breaks, add a line to `docs/decisions.md`.
