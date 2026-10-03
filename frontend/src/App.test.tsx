import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, test, vi } from "vitest"
import App from "./App"

afterEach(() => vi.unstubAllGlobals())

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
