# Frontend: Pages and Style

Status: agreed, updated 2026-10-04. Fits into `app-structure.md`.
Style: Tailwind CSS v4 + shadcn/ui, themed with [globals.css](globals.css) (copy it to `frontend/src/globals.css`). Brand from the brief (Inter, grey scale, red accent `#B61918`), with a modern look since 2026-10-04: light grey canvas, white rounded cards (10px radius), soft shadows, dark slim sidebar. The theme maps the brief's colours onto shadcn's variables, so every shadcn component picks up the look automatically.

## Layout
A dark sidebar on the left (updated 2026-10-04, replaces the top bar). Slim by default: the Stern Stewart logo (`frontend/public/stern-stewart-logo.jpg`, also the favicon) on a white tile and one icon per page. While the pointer or keyboard focus is on it, it widens over the page and shows "Stern Stewart - Document Chat" and the page names. The active page has a red marker. Routes via React Router. The window does not scroll; each page scrolls its own content.
At the top of every page, a red alert when `/api/health` reports a setup problem (for example "ANTHROPIC_API_KEY is missing or invalid" or low Docker memory).

| Route | Page | Purpose |
|---|---|---|
| `/upload` | Upload | Add PDFs |
| `/` | Chat | Ask questions (landing page) |
| `/database` | Database | Inspect what is stored |

## 1. Upload (`/upload`)
- Dropzone for one or more PDFs (click or drag), PDF only, max 10 MB per file; rejects other types and larger files in the browser first (the backend checks again).
- Below it, the list of documents: name, pages, status badge (processing / ready / failed), a progress bar (`chunks_done / chunk_count`) while processing, and a delete button. Polls `GET /api/documents` every few seconds while anything is processing.
- Each file is uploaded in its own request. Duplicate files: one dialog "This document is already uploaded. Overwrite it?" ("These documents ... Overwrite them?" for several) that lists only the files already stored, with Overwrite / Cancel; Overwrite resends only those. Other refusals from the api are listed under the dropzone.
- A failed document shows its error text (for example "encrypted PDF", "no text found", "interrupted, please re-upload").

## 2. Chat (`/`)
- Three columns: sidebar, the chat in the centre (message list above, input pinned to the bottom), and a **History** panel on the right with the old chats (newest first, title = first question; open or delete them) and the "New chat" button. Answer streamed in as it arrives.
- **Inline sources at the end of each sentence or short paragraph**, in the form `[Contract.pdf, p. 12-13, 3.1 Scope]` (document name, page number(s), heading numbers/titles). Shown as small clickable tags; when the model cites several ids in one bracket (`[c2, c3]`), each becomes its own tag. Answers are rendered as markdown (`react-markdown`: bold, lists); a tag that is still arriving is hidden until it is complete.
- How it works: the context given to the answer model labels every chunk with an id (`c12`). The model puts the ids it used (`[c12]`) at the end of the sentence or short paragraph they support, once for several sentences in a row from the same chunks. Before the answer streams, the backend sends a `sources` event mapping each id to document, pages and heading path from the database; the frontend swaps each `[c12]` for its tag as the text arrives. So the names and numbers in the tag always come from stored data and the model cannot invent them. Unknown ids are not shown; text with no valid id after it is a bug we can detect and test for (`uncited_statements`). Each tag also shows the chunk's retrieval score: the rerank score (0-1), with the cosine similarity in the tooltip; the cosine score ("cos 0.61") if the reranker failed; "added" for a chunk added by section selection, which was not scored.
- "Not found in your documents" shown as a normal answer.
- Empty state when no document is ready: a link to the Upload page.
- "New chat" starts an empty conversation; the previous one stays in the History panel. Conversations live in the browser only (`localStorage`); only the newest 10 are kept (`MAX_SAVED_CHATS`). The open chat stays open across page changes and browser restarts, and an answer that is still streaming keeps arriving while another page is shown. The active one's history is sent with each question.
- If the answer call fails, the error is shown as a message in the chat, not as a blank answer.
- While an answer is on its way ("Searching your documents..." until the sources arrive), the input is disabled in every chat, not only the one waiting. "New chat" is disabled while a new chat is already open. Chat titles are the first question, cut to 60 characters.
- Clicking a source tag: first version opens the original PDF at that page in a new tab (`/api/documents/{id}/file#page=12`). The in-page highlighting stays an optional extra.

## 3. Database (`/database`)
Read-only view, so the reviewer and you can see what the pipeline produced. Three levels, drilling down:
1. **Documents:** table with filename, status, pages, section count, chunk count, size, upload date.
2. **Sections:** click a document to see its section tree: each heading indented by its level, with pages and chunk count (the full heading path is not shown on this page).
3. **Chunks:** click a section to see its chunks: text, context sentence, summary, keywords, pages. The embedding vector is not shown, only its presence. Chunks whose enrichment failed are marked "not enriched".
- Read-only: deleting documents is only possible on the Upload page.
- Uses `GET /api/documents/{id}/sections` and `GET /api/sections/{id}/chunks` (in `app-structure.md` §3). Built in build step 5.
- Useful in the demo: it proves each ingestion step (A3–A8) and is the fastest way to debug retrieval.

## Frontend layout
```
frontend/src/
  main.tsx · App.tsx          router + app shell (sidebar, health alert)
  globals.css                 Tailwind + shadcn theme (file above)
  pages/ UploadPage · ChatPage · DatabasePage
  components/ui/              shadcn: button, dialog, table, badge, progress
  components/ Sidebar · PageHeader · Dropzone · DocumentList · DuplicateDialog · StatusBadge · MessageList · Composer · ChatHistory · CitationChip · SectionTree · ChunkList · SetupBanner
  hooks/ useHealth · useDocuments · useFetched
  components/ConversationsProvider   old chats in localStorage, held above the routes
  lib/ citations · upload · pages · utils   citation parsing, browser file checks, page ranges, class names
  api/ client.ts              typed fetch wrappers + SSE reader (sources, text, error; ends when the stream closes)
```
shadcn components are copied into the repo (`components/ui/`), so they are our code and can be explained. Tailwind classes style the pages. Plain-CSS alternative was considered and rejected: the dialog, table and keyboard handling would be hand-built.

## Decisions
- Delete documents only on the Upload page.
- Chat always shows sources at the end of each sentence or short paragraph (document, pages, headings).
- Styling: Tailwind v4 + shadcn/ui, themed from the brief.
