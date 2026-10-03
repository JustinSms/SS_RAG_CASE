import { useEffect, useState } from "react"

// Loads `fetcher(id)` whenever `id` changes; `id` null means nothing is selected.
// A slow reply for an earlier selection is ignored.
export function useFetched<T>(id: string | null, fetcher: (id: string) => Promise<T>) {
  const [state, setState] = useState<{ id: string; data?: T; error?: string } | null>(null)

  useEffect(() => {
    if (id === null) return
    let current = true
    fetcher(id)
      .then((data) => current && setState({ id, data }))
      .catch((e: Error) => current && setState({ id, error: e.message }))
    return () => {
      current = false
    }
  }, [id, fetcher])

  // Until the reply for the current id arrives, there is no data (not the previous one's).
  const ready = id !== null && state?.id === id
  return { data: ready ? state.data : undefined, error: ready ? state.error : undefined }
}
