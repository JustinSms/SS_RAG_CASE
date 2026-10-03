import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, test, vi } from "vitest"
import App from "./App"

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

function stubHealth(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({ ok: true, json: async () => (url === "/api/health" ? body : []) })),
  )
}

function renderApp() {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  )
}

test("shows no banner when health has no problems", async () => {
  stubHealth({ healthy: true, problems: [] })
  renderApp()
  expect(await screen.findByLabelText("Question")).toBeInTheDocument()
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
})

test("shows the banner with the problem message", async () => {
  stubHealth({
    healthy: false,
    problems: [{ code: "api_key_missing", level: "error", message: "ANTHROPIC_API_KEY is not set." }],
  })
  renderApp()
  expect(await screen.findByRole("alert")).toHaveTextContent("ANTHROPIC_API_KEY is not set.")
})

test("shows the banner when the api cannot be reached", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")))
  renderApp()
  expect(await screen.findByRole("alert")).toHaveTextContent("not reachable")
})

test("has the three nav links", () => {
  stubHealth({ healthy: true, problems: [] })
  renderApp()
  for (const name of ["Chat", "Upload", "Database"]) {
    expect(screen.getByRole("link", { name })).toBeInTheDocument()
  }
})

test("the open chat and a streaming answer survive a page change", async () => {
  // The answer only arrives once the test lets it, after leaving the Chat page.
  let finish = () => {}
  const encoder = new TextEncoder()
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode("event: sources\ndata: {}\n\n"))
      finish = () => {
        controller.enqueue(encoder.encode('event: text\ndata: "Thirty days."\n\nevent: done\ndata: {}\n\n'))
        controller.close()
      }
    },
  })
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url === "/api/chat"
        ? { ok: true, body }
        : { ok: true, json: async () => (url === "/api/health" ? { healthy: true, problems: [] } : []) },
    ),
  )
  renderApp()
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Notice period?" } })
  fireEvent.click(screen.getByRole("button", { name: "Send" }))
  await screen.findAllByText("Notice period?")

  fireEvent.click(screen.getByRole("link", { name: "Upload" }))
  expect(screen.queryByLabelText("Question")).not.toBeInTheDocument()
  finish()
  fireEvent.click(screen.getByRole("link", { name: "Chat" }))
  expect(await screen.findByText("Thirty days.")).toBeInTheDocument()
})
