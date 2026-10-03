import type { Health } from "@/api/client"

type Props = { health: Health | null; error: string | null }

export function ChatPage({ health, error }: Props) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl">Chat</h1>
      {error ? (
        <p className="text-destructive">Backend not reachable: {error}</p>
      ) : health?.healthy ? (
        <p className="text-success">Backend ready</p>
      ) : health ? (
        <p className="text-muted-foreground">Backend not ready, see the banner above.</p>
      ) : (
        <p className="text-muted-foreground">Checking backend...</p>
      )}
    </div>
  )
}
