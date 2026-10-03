import { MessageSquare, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Conversation } from "@/components/ConversationsProvider"
import { cn } from "@/lib/utils"

type Props = {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  const today = new Date().toDateString() === date.toDateString()
  return today
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString([], { day: "numeric", month: "short" })
}

// Right-hand panel: the old chats of this browser, newest first.
export function ChatHistory({ conversations, activeId, onSelect, onNew, onDelete }: Props) {
  return (
    <aside className="hidden w-72 shrink-0 flex-col border-l bg-background lg:flex">
      <div className="flex h-16 items-center justify-between border-b px-4">
        <h2 className="text-sm">History</h2>
        <Button variant="outline" size="sm" onClick={onNew} disabled={activeId === null}>
          <Plus />
          New chat
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">Your chats will appear here.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  aria-current={c.id === activeId}
                  className={cn(
                    "flex w-full items-start gap-2.5 rounded-lg py-2 pr-9 pl-3 text-left transition-colors hover:bg-muted",
                    c.id === activeId && "bg-accent hover:bg-accent",
                  )}
                >
                  <MessageSquare
                    className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground", c.id === activeId && "text-primary")}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{c.title}</span>
                    <span className="block text-xs text-muted-foreground">{formatDate(c.updatedAt)}</span>
                  </span>
                </button>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Delete chat ${c.title}`}
                  onClick={() => onDelete(c.id)}
                  className="absolute top-2 right-2 text-muted-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
