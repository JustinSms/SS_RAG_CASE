import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, test, vi } from "vitest"
import { CONVERSATIONS_KEY, ConversationsProvider, MAX_SAVED_CHATS } from "@/components/ConversationsProvider"
import { ChatPage } from "./ChatPage"

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

const READY = { id: "d1", filename: "Contract.pdf", status: "ready", chunks_done: 0 }
const SOURCE = {
  label: "c1",
  document_id: "d1",
  filename: "Contract.pdf",
  page_start: 12,
  page_end: 13,
  heading_path: "3.1 Scope",
}

// A /api/chat response whose body arrives in the given pieces (they may cut an event in two).
function sse(...pieces: string[]) {
  const encoder = new TextEncoder()
  const body = new ReadableStream({
    start(controller) {
      for (const piece of pieces) controller.enqueue(encoder.encode(piece))
      controller.close()
    },
  })
  return { ok: true, body }
}

const event = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`

function stubApi(documents: unknown[], chat: () => unknown) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/documents") return { ok: true, json: async () => documents }
    return chat()
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function renderChat() {
  return render(
    <MemoryRouter>
      <ConversationsProvider>
        <ChatPage />
      </ConversationsProvider>
    </MemoryRouter>,
  )
}

async function ask(question: string) {
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } })
  fireEvent.click(screen.getByRole("button", { name: "Send" }))
}

test("shows the answer with the source tag from the stored source", async () => {
  stubApi([READY], () =>
    sse(event("sources", { c1: SOURCE }), event("text", "Thirty days. "), event("text", "[c1]"), event("done", {})),
  )
  renderChat()
  await ask("Notice period?")

  const tag = await screen.findByRole("link", { name: "[Contract.pdf, p. 12-13, 3.1 Scope]" })
  expect(tag).toHaveAttribute("href", "/api/documents/d1/file#page=12")
  expect(screen.getByText("Thirty days.")).toBeInTheDocument()
})

test("shows the retrieval score on each source tag", async () => {
  const scored = { ...SOURCE, cosine: 0.612, rerank: 0.8249 }
  const selected = { ...SOURCE, label: "c2", page_start: 14, page_end: 14, cosine: null, rerank: null }
  stubApi([READY], () =>
    sse(event("sources", { c1: scored, c2: selected }), event("text", "Thirty days. [c1, c2]"), event("done", {})),
  )
  renderChat()
  await ask("Notice period?")

  expect(await screen.findByText("0.82")).toHaveAccessibleName("Rerank score 0.82, cosine similarity 0.61")
  expect(screen.getByText("added")).toHaveAccessibleName("Added by section selection (not scored)")
})

test("shows an error as a message and New chat clears the conversation", async () => {
  stubApi([READY], () => ({ ok: false, status: 502, json: async () => ({ detail: "Model unreachable" }) }))
  renderChat()
  await ask("Notice period?")

  expect(await screen.findByText("Model unreachable")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "New chat" }))
  expect(screen.queryByText("Model unreachable")).not.toBeInTheDocument()
})

test("links to the Upload page when no document is ready", async () => {
  stubApi([], () => ({ ok: true, json: async () => ({}) }))
  renderChat()
  expect(await screen.findByRole("link", { name: "Upload a PDF" })).toHaveAttribute("href", "/upload")
})

test("a tag cut in two by the network never shows as raw text", async () => {
  const unfinished = event("text", "Thirty days. [c")
  // The first piece ends in the middle of the second text event.
  const [head, tail] = [unfinished.slice(0, 20), unfinished.slice(20)]
  stubApi([READY], () =>
    sse(event("sources", { c1: SOURCE }), head, tail, event("text", "1]"), event("done", {})),
  )
  renderChat()
  await ask("Notice period?")

  expect(await screen.findByRole("link", { name: "[Contract.pdf, p. 12-13, 3.1 Scope]" })).toBeInTheDocument()
  expect(screen.queryByText(/\[c/)).not.toBeInTheDocument()
})

test("ids that are not in the sources are not shown", async () => {
  stubApi([READY], () =>
    sse(event("sources", { c1: SOURCE }), event("text", "Real. [c1] Invented. [c9]"), event("done", {})),
  )
  renderChat()
  await ask("Notice period?")

  expect(await screen.findAllByRole("link")).toHaveLength(1)
  expect(screen.queryByText(/c9/)).not.toBeInTheDocument()
})

test("an error event replaces the half-written answer", async () => {
  stubApi([READY], () =>
    sse(event("sources", { c1: SOURCE }), event("text", "Thirty "), event("error", "Model unreachable")),
  )
  renderChat()
  await ask("Notice period?")

  expect(await screen.findByText("Model unreachable")).toBeInTheDocument()
  expect(screen.queryByText(/Thirty/)).not.toBeInTheDocument()
})

test("an old chat stays in the history and opens again", async () => {
  stubApi([READY], () => sse(event("sources", { c1: SOURCE }), event("text", "Thirty days. [c1]"), event("done", {})))
  renderChat()
  await ask("Notice period?")
  await screen.findByText("Thirty days.")

  fireEvent.click(screen.getByRole("button", { name: "New chat" }))
  expect(screen.queryByText("Thirty days.")).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: /^Notice period\?/ }))
  expect(screen.getByText("Thirty days.")).toBeInTheDocument()
})

test("old chats are kept after a reload and can be deleted", async () => {
  stubApi([READY], () => sse(event("sources", { c1: SOURCE }), event("text", "Thirty days. [c1]"), event("done", {})))
  const { unmount } = renderChat()
  await ask("Notice period?")
  await screen.findByText("Thirty days.")
  unmount()

  // After a restart the chat that was open is open again.
  renderChat()
  expect(screen.getByText("Thirty days.")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Delete chat Notice period?" }))
  expect(screen.queryByText("Thirty days.")).not.toBeInTheDocument()
  expect(screen.getByText("Your chats will appear here.")).toBeInTheDocument()
})

test("only the newest chats are kept", async () => {
  const old = Array.from({ length: MAX_SAVED_CHATS }, (_, i) => ({
    id: `old${i}`,
    title: `Old question ${i}`,
    updatedAt: "2026-10-01T10:00:00Z",
    messages: [{ role: "user", content: `Old question ${i}` }],
  }))
  localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(old))
  stubApi([READY], () => sse(event("sources", { c1: SOURCE }), event("text", "Thirty days. [c1]"), event("done", {})))
  renderChat()
  await ask("Notice period?")
  await screen.findByText("Thirty days.")

  const saved = JSON.parse(localStorage.getItem(CONVERSATIONS_KEY)!)
  expect(saved).toHaveLength(MAX_SAVED_CHATS)
  expect(saved[0].title).toBe("Notice period?")
  expect(screen.queryByText(`Old question ${MAX_SAVED_CHATS - 1}`)).not.toBeInTheDocument()
  expect(screen.getByText("Old question 0")).toBeInTheDocument()
})
