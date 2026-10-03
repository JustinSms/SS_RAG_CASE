import { useCallback, useEffect, useState } from "react"
import { listDocuments, type Document } from "@/api/client"

export const DOCUMENT_POLL_MS = 3000

// The document list, refreshed every few seconds while any document is still processing.
export function useDocuments() {
  const [documents, setDocuments] = useState<Document[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(
    () =>
      listDocuments()
        .then((result) => (setDocuments(result), setError(null)))
        .catch((e: Error) => setError(e.message)),
    [],
  )

  useEffect(() => {
    refresh()
  }, [refresh])

  const processing = documents?.some((d) => d.status === "processing") ?? false
  useEffect(() => {
    if (!processing) return
    const timer = setInterval(refresh, DOCUMENT_POLL_MS)
    return () => clearInterval(timer)
  }, [processing, refresh])

  return { documents, error, refresh }
}
