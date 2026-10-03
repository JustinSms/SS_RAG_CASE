import type { Source } from "@/api/client"
import { CitationChip } from "@/components/CitationChip"
import { splitAnswer } from "@/lib/citations"
import { cn } from "@/lib/utils"

export type ChatMessage = {
  role: "user" | "assistant"
  content: string
  sources?: Record<string, Source>
  error?: boolean
}

function Answer({ message }: { message: ChatMessage }) {
  return splitAnswer(message.content).map((part, i) =>
    typeof part === "string" ? (
      <span key={i}>{part}</span>
    ) : (
      part.ids.map((id) => {
        const source = message.sources?.[id]
        return source && <CitationChip key={`${i}-${id}`} source={source} />
      })
    ),
  )
}

export function MessageList({ messages, waiting }: { messages: ChatMessage[]; waiting: boolean }) {
  return (
    <ul className="space-y-4">
      {messages.map((message, i) => (
        <li key={i} className={cn("flex", message.role === "user" && "justify-end")}>
          <div
            className={cn(
              "max-w-[85%] whitespace-pre-wrap rounded-md px-4 py-2",
              message.role === "user" ? "bg-secondary" : "bg-card",
              message.error && "border border-destructive text-destructive",
            )}
          >
            {message.role === "assistant" && !message.error ? <Answer message={message} /> : message.content}
          </div>
        </li>
      ))}
      {waiting && <li className="text-sm text-muted-foreground">Thinking...</li>}
    </ul>
  )
}
