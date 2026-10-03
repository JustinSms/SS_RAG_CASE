import { CircleAlert, Sparkles } from "lucide-react"
import type { Source } from "@/api/client"
import { CitationChip } from "@/components/CitationChip"
import { hideOpenCitation, splitAnswer } from "@/lib/citations"
import { cn } from "@/lib/utils"

export type ChatMessage = {
  role: "user" | "assistant"
  content: string
  sources?: Record<string, Source>
  error?: boolean
  streaming?: boolean
}

function Answer({ message }: { message: ChatMessage }) {
  return splitAnswer(message.streaming ? hideOpenCitation(message.content) : message.content).map((part, i) =>
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

function Avatar({ error }: { error?: boolean }) {
  return (
    <span
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground",
        error && "bg-accent text-primary",
      )}
    >
      {error ? <CircleAlert className="size-4" /> : <Sparkles className="size-4" />}
    </span>
  )
}

export function MessageList({ messages, waiting }: { messages: ChatMessage[]; waiting: boolean }) {
  return (
    <ul className="space-y-6">
      {messages.map((message, i) =>
        message.role === "user" ? (
          <li key={i} className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-br-md bg-sidebar px-4 py-2.5 whitespace-pre-wrap text-sidebar-foreground">
              {message.content}
            </div>
          </li>
        ) : (
          <li key={i} className="flex gap-3">
            <Avatar error={message.error} />
            <div
              className={cn(
                "min-w-0 flex-1 pt-1 leading-relaxed whitespace-pre-wrap",
                message.error && "rounded-xl border border-primary/20 bg-accent px-4 py-2.5 pt-2.5 text-accent-foreground",
              )}
            >
              {message.error ? message.content : <Answer message={message} />}
              {message.streaming && (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-primary align-middle" />
              )}
            </div>
          </li>
        ),
      )}
      {waiting && messages[messages.length - 1]?.role === "user" && (
        <li className="flex items-center gap-3">
          <Avatar />
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="flex gap-1">
              {[0, 150, 300].map((delay) => (
                <span
                  key={delay}
                  className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </span>
            Searching your documents...
          </span>
        </li>
      )}
    </ul>
  )
}
