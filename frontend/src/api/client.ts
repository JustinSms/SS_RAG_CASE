export type Problem = {
  code: string
  level: "error" | "warning"
  message: string
}

export type Health = {
  healthy: boolean
  problems: Problem[]
}

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health")
  if (!response.ok) throw new Error(`Health check failed (${response.status})`)
  return response.json()
}

export type DocumentStatus = "processing" | "ready" | "failed"

export type Document = {
  id: string
  filename: string
  size_bytes: number
  status: DocumentStatus
  error: string | null
  page_count: number | null
  chunk_count: number | null
  chunks_done: number
  created_at: string
}

// The api reports errors as {detail: "..."}; fall back to the status code otherwise.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === "string") return body.detail
  } catch {
    // body was not JSON
  }
  return `Request failed (${response.status})`
}

export async function listDocuments(): Promise<Document[]> {
  const response = await fetch("/api/documents")
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

export async function uploadDocuments(files: File[]): Promise<void> {
  const body = new FormData()
  for (const file of files) body.append("files", file)
  const response = await fetch("/api/documents", { method: "POST", body })
  // 409 (already uploaded) arrives with its own message; the overwrite dialog comes later.
  if (!response.ok) throw new Error(await errorMessage(response))
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`/api/documents/${id}`, { method: "DELETE" })
  if (!response.ok) throw new Error(await errorMessage(response))
}

export type Source = {
  label: string
  document_id: string
  filename: string
  page_start: number
  page_end: number
  heading_path: string
}

export type HistoryMessage = { role: "user" | "assistant"; content: string }

export type ChatAnswer = { answer: string; sources: Record<string, Source> }

export async function askQuestion(question: string, history: HistoryMessage[]): Promise<ChatAnswer> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}
