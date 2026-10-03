# Frontend: Pages and Style

Status: agreed, updated 2026-10-03. Fits into `app-structure.md`.
Style: Tailwind CSS v4 + shadcn/ui, themed with [globals.css](globals.css) (copy it to `frontend/src/globals.css`), taken from the Siteco brief: Inter, grey scale, red accent `#B61918`, near-square corners, dark header. The theme maps the brief's colours onto shadcn's variables, so every shadcn component picks up the look automatically.

## Layout
One dark top bar (brand left, three nav links right of it, active link underlined in red). Routes via React Router.
Below the bar, a red banner on every page when `/api/health` reports a setup problem (for example "ANTHROPIC_API_KEY is missing or invalid" or low Docker memory).

| Route | Page | Purpose |
|---|---|---|
| `/upload` | Upload | Add PDFs |
| `/` | Chat | Ask questions (landing page) |
| `/database` | Database | Inspect what is stored |

## 1. Upload (`/upload`)
- Dropzone for one or more PDFs (click or drag), PDF only, max 10 MB per file; rejects other types and larger files in the browser first (the backend checks again).
- Below it, the list of documents: name, pages, status badge (processing / ready / failed), a progress bar (`chunks_done / chunk_count`) while processing, and a delete button. Polls `GET /api/documents` every few seconds while anything is processing.
- Duplicate file: dialog "This document is already uploaded. Overwrite it?" with Overwrite / Cancel.
- A failed document shows its error text (for example "encrypted PDF", "no text found", "interrupted, please re-upload").

## 2. Chat (`/`)
- Message list, input at the bottom, answer streamed in as it arrives.
- **Inline sources after each statement**, in the form `[Contract.pdf, p. 12-13, 3.1 Scope]` (document name, page number(s), heading numbers/titles). Several sources are listed in one bracket. Shown as small clickable tags.
- How it works: the context given to the answer model labels every chunk with an id (`c12`). The model must end each statement with the ids it used (`[c12]`). Before the answer streams, the backend sends a `sources` event mapping each id to document, pages and heading path from the database; the frontend swaps each `[c12]` for its tag as the text arrives. So the names and numbers in the tag always come from stored data and the model cannot invent them. Unknown ids are dropped; a statement without a valid id is a bug we can detect and test for.
- "Not found in your documents" shown as a normal answer.
- Empty state when no document is ready: a link to the Upload page.
- "New chat" button clears the conversation. History lives in the browser only and is sent with each question.
- If the answer call fails, the error is shown as a message in the chat, not as a blank answer.
- Clicking a source tag: first version opens the original PDF at that page in a new tab (`/api/documents/{id}/file#page=12`). The in-page highlighting stays an optional extra.

## 3. Database (`/database`)
Read-only view, so the reviewer and you can see what the pipeline produced. Three levels, drilling down:
1. **Documents:** table with filename, status, pages, section count, chunk count, size, upload date.
2. **Sections:** click a document to see its section tree (heading path, pages, chunk count).
3. **Chunks:** click a section to see its chunks: text, context sentence, summary, keywords, pages. The embedding vector is not shown, only its presence. Chunks whose enrichment failed are marked "not enriched".
- Read-only: deleting documents is only possible on the Upload page.
- Uses `GET /api/documents/{id}/sections` and `GET /api/sections/{id}/chunks` (in `app-structure.md` §3). Built in build step 5.
- Useful in the demo: it proves each ingestion step (A3–A8) and is the fastest way to debug retrieval.

## Frontend layout
```
frontend/src/
  main.tsx · App.tsx          router + app shell (header, nav)
  globals.css                 Tailwind + shadcn theme (file above)
  pages/ UploadPage · ChatPage · DatabasePage
  components/ui/              shadcn: button, dialog, table, badge, progress, input, textarea, tooltip
  components/ Dropzone · DocumentList · DuplicateDialog · MessageList · Composer · CitationChip · SectionTree · ChunkTable · SetupBanner
  api/ client.ts              typed fetch wrappers + SSE reader (sources, text, done)
```
shadcn components are copied into the repo (`components/ui/`), so they are our code and can be explained. Tailwind classes style the pages. Plain-CSS alternative was considered and rejected: the dialog, table and keyboard handling would be hand-built.

## Decisions
- Delete documents only on the Upload page.
- Chat always shows sources after each statement (document, pages, headings).
- Styling: Tailwind v4 + shadcn/ui, themed from the brief.
