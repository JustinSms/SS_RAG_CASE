import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import { DatabasePage } from "./DatabasePage"

afterEach(() => vi.unstubAllGlobals())

const DOCUMENT = {
  id: "d1",
  filename: "Contract.pdf",
  size_bytes: 2 * 1024 * 1024,
  status: "ready",
  error: null,
  page_count: 12,
  chunk_count: 3,
  chunks_done: 3,
  created_at: "2026-10-03T10:00:00Z",
  section_count: 2,
}

const SECTIONS = [
  { id: "s1", parent_id: null, heading: "1 Scope", level: 1, heading_path: "1 Scope",
    page_start: 1, page_end: 2, chunk_count: 2 },
  { id: "s2", parent_id: "s1", heading: "1.1 Data", level: 2, heading_path: "1 Scope > 1.1 Data",
    page_start: 2, page_end: 2, chunk_count: 1 },
]

const CHUNKS = [
  { id: "c1", position_in_section: 0, text: "Alpha clause", context: "About alpha", summary: "Alpha summary",
    keywords: ["alpha", "clause"], enriched: true, page_start: 1, page_end: 2, has_embedding: true },
  { id: "c2", position_in_section: 1, text: "Beta clause", context: null, summary: null,
    keywords: null, enriched: false, page_start: 2, page_end: 2, has_embedding: false },
]

function stubApi() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    // The page only reads: any POST or DELETE gets no answer.
    const body = init?.method ? null : url === "/api/documents" ? [DOCUMENT]
      : url === "/api/documents/d1/sections" ? SECTIONS
      : url === "/api/sections/s1/chunks" ? CHUNKS
      : null
    return { ok: body !== null, status: body ? 200 : 404, json: async () => body }
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

test("drills down from document to sections to chunks", async () => {
  const fetchMock = stubApi()
  render(<DatabasePage />)

  // Level 1: the numbers of the document row.
  const row = (await screen.findByText("Contract.pdf")).closest("tr")!
  expect(row).toHaveTextContent("12")
  expect(row).toHaveTextContent("2.0 MB")
  expect(screen.queryByText(/Sections of/)).not.toBeInTheDocument()

  // Level 2
  fireEvent.click(screen.getByText("Contract.pdf"))
  fireEvent.click(await screen.findByText("1 Scope"))
  expect(screen.getByText("1.1 Data")).toBeInTheDocument()
  expect(screen.getByText("2 chunks")).toBeInTheDocument()

  // Level 3: text, context, summary, keywords, pages, the not-enriched marker and the embedding flags.
  expect(await screen.findByText("Alpha clause")).toBeInTheDocument()
  expect(screen.getByText("About alpha")).toBeInTheDocument()
  expect(screen.getByText("Alpha summary")).toBeInTheDocument()
  expect(screen.getByText("alpha, clause")).toBeInTheDocument()
  expect(screen.getAllByText("p. 1-2")).toHaveLength(2) // the section row and the chunk row
  expect(screen.getAllByText("not enriched")).toHaveLength(1)
  expect(screen.getByText("yes")).toBeInTheDocument()
  expect(screen.getByText("no")).toBeInTheDocument()

  // Read-only: nothing here deletes.
  expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.every(([, init]) => init?.method === undefined)).toBe(true)
})

test("choosing another document clears the chunks of the old one", async () => {
  stubApi()
  render(<DatabasePage />)
  fireEvent.click(await screen.findByText("Contract.pdf"))
  fireEvent.click(await screen.findByText("1 Scope"))
  await screen.findByText("Alpha clause")

  fireEvent.click(screen.getByText("Contract.pdf"))
  expect(screen.queryByText("Alpha clause")).not.toBeInTheDocument()
})

test("shows a message when there are no documents", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => [] })))
  render(<DatabasePage />)
  expect(await screen.findByText("No documents yet.")).toBeInTheDocument()
})
