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
