import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import type { Document } from "@/api/client"
import { UploadPage } from "./UploadPage"

afterEach(() => vi.unstubAllGlobals())

function doc(overrides: Partial<Document>): Document {
  return {
    id: "1",
    filename: "a.pdf",
    size_bytes: 100,
    status: "ready",
    error: null,
    page_count: 3,
    chunk_count: 5,
    chunks_done: 0,
    created_at: "2026-10-03T10:00:00Z",
    ...overrides,
  }
}

function reply(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body }
}

// Routes fetch calls by method; `list` can change between calls to mimic processing -> ready.
function stubApi(handlers: { list: () => Document[]; post?: unknown; del?: unknown }) {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") return handlers.post ?? reply(202, {})
    if (init?.method === "DELETE") return handlers.del ?? reply(204, {})
    return reply(200, handlers.list())
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function pick(...files: File[]) {
  fireEvent.change(screen.getByTestId("file-input"), { target: { files } })
}

const pdf = (name = "x.pdf", size = 10) =>
  new File([new Uint8Array(size)], name, { type: "application/pdf" })

test("lists documents with pages, status and the error of a failed one", async () => {
  stubApi({
    list: () => [
      doc({ id: "1", filename: "a.pdf", page_count: 3 }),
      doc({ id: "2", filename: "b.pdf", status: "failed", error: "no text found", page_count: null }),
    ],
  })
  render(<UploadPage />)
  expect(await screen.findByText("a.pdf")).toBeInTheDocument()
  expect(screen.getByText("3 pages")).toBeInTheDocument()
  expect(screen.getByText("ready")).toBeInTheDocument()
  expect(screen.getByText("failed")).toBeInTheDocument()
  expect(screen.getByText("no text found")).toBeInTheDocument()
})

test("rejects a .docx and a file over 10 MB in the browser without calling the api", async () => {
  const fetchMock = stubApi({ list: () => [] })
  render(<UploadPage />)
  await screen.findByText("No documents yet.")
  const big = pdf("big.pdf", 15 * 1024 * 1024)
  const docx = new File(["x"], "notes.docx", {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  })
  pick(big, docx)
  expect(await screen.findByText("big.pdf is larger than 10 MB.")).toBeInTheDocument()
  expect(screen.getByText("notes.docx is not a PDF.")).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false)
})

test("uploads valid files in one request and refreshes the list", async () => {
  let documents: Document[] = []
  const fetchMock = stubApi({ list: () => documents })
  render(<UploadPage />)
  await screen.findByText("No documents yet.")
  documents = [doc({ filename: "x.pdf" }), doc({ id: "2", filename: "y.pdf" })]
  pick(pdf("x.pdf"), pdf("y.pdf"))
  expect(await screen.findByText("y.pdf")).toBeInTheDocument()
  const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!
  expect((post[1]!.body as FormData).getAll("files")).toHaveLength(2)
})

test("shows the api message for a duplicate (409)", async () => {
  stubApi({ list: () => [], post: reply(409, { detail: "x.pdf is already uploaded.", document: null }) })
  render(<UploadPage />)
  await screen.findByText("No documents yet.")
  pick(pdf("x.pdf"))
  expect(await screen.findByRole("alert")).toHaveTextContent("x.pdf is already uploaded.")
})

test("polls while a document is processing and stops once it is ready", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    let status: Document["status"] = "processing"
    const fetchMock = stubApi({ list: () => [doc({ status })] })
    render(<UploadPage />)
    expect(await screen.findByText("processing")).toBeInTheDocument()
    status = "ready"
    await vi.advanceTimersByTimeAsync(3500)
    expect(await screen.findByText("ready")).toBeInTheDocument()
    const calls = fetchMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchMock.mock.calls.length).toBe(calls)
  } finally {
    vi.useRealTimers()
  }
})

test("delete calls the api and refreshes the list", async () => {
  let documents = [doc({ filename: "a.pdf" })]
  const fetchMock = stubApi({ list: () => documents })
  render(<UploadPage />)
  fireEvent.click(await screen.findByRole("button", { name: "Delete a.pdf" }))
  documents = []
  await waitFor(() => expect(screen.getByText("No documents yet.")).toBeInTheDocument())
  expect(fetchMock).toHaveBeenCalledWith("/api/documents/1", { method: "DELETE" })
})
