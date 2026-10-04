import { CircleAlert, Sparkles } from "lucide-react"
import type { Source } from "@/api/client"
import { CitationChip } from "@/components/CitationChip"
import ReactMarkdown, { defaultUrlTransform } from "react-markdown"
import { CITATION_SCHEME, citationsToLinks, hideOpenCitation } from "@/lib/citations"
import { cn } from "@/lib/utils"

export type ChatMessage = {
  role: "user" | "assistant"
  content: string
  sources?: Record<string, Source>
  error?: boolean
  streaming?: boolean
}

// Markdown links with the cite: scheme are citations; show each cited source as a chip.
function Answer({ message }: { message: ChatMessage }) {
  const text = message.streaming ? hideOpenCitation(message.content) : message.content
  return (
    <ReactMarkdown
      urlTransform={(url) => (url.startsWith(CITATION_SCHEME) ? url : defaultUrlTransform(url))}
      components={{
        a: ({ href, children, ...props }) =>
          href?.startsWith(CITATION_SCHEME) ? (
            href
              .slice(CITATION_SCHEME.length)
              .split(",")
              .map((id) => {
                const source = message.sources?.[id]
                return source && <CitationChip key={id} source={source} />
              })
          ) : (
            <a href={href} target="_blank" rel="noreferrer" {...props}>
              {children}
            </a>
          ),
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-6 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-6 last:mb-0">{children}</ol>,
      }}
    >
      {citationsToLinks(text)}
    </ReactMarkdown>
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
                "min-w-0 flex-1 pt-1 leading-relaxed",
                message.error && "whitespace-pre-wrap",
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
