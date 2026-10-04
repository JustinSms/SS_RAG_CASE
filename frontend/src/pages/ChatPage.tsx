import { useEffect, useRef } from "react"
import { FileSearch, Upload } from "lucide-react"
import { Link } from "react-router-dom"
import { askQuestion, type HistoryMessage } from "@/api/client"
import { ChatHistory } from "@/components/ChatHistory"
import { Composer } from "@/components/Composer"
import { useConversations } from "@/components/ConversationsProvider"
import { MessageList, type ChatMessage } from "@/components/MessageList"
import { useDocuments } from "@/hooks/useDocuments"

// Past turns for the backend: no error messages, and no question whose answer failed.
function historyOf(messages: ChatMessage[]): HistoryMessage[] {
  return messages
    .filter((m, i) => !m.error && !messages[i + 1]?.error)
    .map(({ role, content }) => ({ role, content }))
}

function EmptyState({ noReadyDocuments }: { noReadyDocuments: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-primary">
        <FileSearch className="size-7" />
      </span>
      <div className="space-y-1.5">
        <h1 className="text-2xl">Ask your documents</h1>
        <p className="max-w-md text-muted-foreground">
          Answers are grounded in your uploaded PDFs, with source tags that open the cited page.
        </p>
      </div>
      {noReadyDocuments && (
        <p className="flex items-center gap-2 rounded-xl border bg-background px-4 py-3 text-sm text-muted-foreground shadow-card">
          <Upload className="size-4 text-primary" />
          No documents are ready yet.
          <Link to="/upload" className="font-medium text-primary hover:underline">Upload a PDF</Link>
          to start asking questions.
        </p>
      )}
    </div>
  )
}

export function ChatPage() {
  const { documents } = useDocuments()
  const { conversations, active, setActiveId, waitingId, setWaitingId, create, update, remove } = useConversations()
  const activeId = active?.id ?? null
  const scroller = useRef<HTMLDivElement>(null)

  const messages = active?.messages ?? []
  const noReadyDocuments = documents !== null && !documents.some((d) => d.status === "ready")

  // Keep the newest text in view while the answer streams.
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight
  }, [active?.messages])

  async function send(question: string) {
    const history = historyOf(messages)
    const id = activeId ?? create(question)
    setActiveId(id)
    update(id, (current) => [...current, { role: "user", content: question }])
    setWaitingId(id)
    // The answer is the last message while it streams.
    const updateAnswer = (change: (answer: ChatMessage) => ChatMessage) =>
      update(id, (current) => [...current.slice(0, -1), change(current[current.length - 1])])
    let answering = false
    try {
      await askQuestion(question, history, {
        onSources: (sources) => {
          answering = true
          update(id, (current) => [...current, { role: "assistant", content: "", sources, streaming: true }])
        },
        onText: (text) => updateAnswer((answer) => ({ ...answer, content: answer.content + text })),
      })
      updateAnswer((answer) => ({ ...answer, streaming: false }))
    } catch (e) {
      // A half-written answer is replaced by the error.
      update(id, (current) => [
        ...(answering ? current.slice(0, -1) : current),
        { role: "assistant", content: (e as Error).message, error: true },
      ])
    } finally {
      setWaitingId(null)
    }
  }

  return (
    <div className="flex h-full">
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center border-b bg-background/80 px-6 backdrop-blur">
          <p className="truncate font-semibold">{active?.title ?? "New chat"}</p>
        </header>
        <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto h-full max-w-3xl px-6 py-8">
            {messages.length === 0 ? (
              <EmptyState noReadyDocuments={noReadyDocuments} />
            ) : (
              <MessageList messages={messages} waiting={waitingId !== null && waitingId === activeId} />
            )}
          </div>
        </div>
        <div className="shrink-0 px-6 pt-2 pb-10">
          <div className="mx-auto max-w-3xl">
            <Composer disabled={waitingId !== null} onSend={send} />
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Enter to send, Shift + Enter for a new line. Every answer cites its sources.
            </p>
          </div>
        </div>
      </section>
      <ChatHistory
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={() => setActiveId(null)}
        onDelete={remove}
      />
    </div>
  )
}
