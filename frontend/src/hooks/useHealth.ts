import { useEffect, useState } from "react"
import { getHealth, type Health } from "@/api/client"

export const HEALTH_POLL_MS = 5000

// Health as seen by the browser: `error` is set when the api cannot be reached at all.
export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const check = () =>
      getHealth()
        .then((result) => active && (setHealth(result), setError(null)))
        .catch((e: Error) => active && setError(e.message))
    check()
    const timer = setInterval(check, HEALTH_POLL_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  return { health, error }
}
