import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, test, vi } from "vitest"
import { ChatPage } from "./ChatPage"

afterEach(() => vi.unstubAllGlobals())

const READY = { id: "d1", filename: "Contract.pdf", status: "ready", chunks_done: 0 }
const SOURCE = {
  label: "c1",
  document_id: "d1",
  filename: "Contract.pdf",
  page_start: 12,
  page_end: 13,
  heading_path: "3.1 Scope",
}

function stubApi(documents: unknown[], chat: () => unknown) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/documents") return { ok: true, json: async () => documents }
    return chat()
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function renderChat() {
  render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  )
}

async function ask(question: string) {
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } })
  fireEvent.click(screen.getByRole("button", { name: "Send" }))
}

test("shows the answer with the source tag from the stored source", async () => {
  stubApi([READY], () => ({
    ok: true,
    json: async () => ({ answer: "Thirty days. [c1]", sources: { c1: SOURCE } }),
  }))
  renderChat()
  await ask("Notice period?")

  const tag = await screen.findByRole("link", { name: "[Contract.pdf, p. 12-13, 3.1 Scope]" })
  expect(tag).toHaveAttribute("href", "/api/documents/d1/file#page=12")
  expect(screen.getByText("Thirty days.")).toBeInTheDocument()
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
