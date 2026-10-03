import { useState } from "react"
import { Link } from "react-router-dom"
import { askQuestion, type HistoryMessage } from "@/api/client"
import { Composer } from "@/components/Composer"
import { MessageList, type ChatMessage } from "@/components/MessageList"
import { Button } from "@/components/ui/button"
import { useDocuments } from "@/hooks/useDocuments"

// Past turns for the backend: no error messages, and no question whose answer failed.
function historyOf(messages: ChatMessage[]): HistoryMessage[] {
  return messages
    .filter((m, i) => !m.error && !messages[i + 1]?.error)
    .map(({ role, content }) => ({ role, content }))
}

export function ChatPage() {
  const { documents } = useDocuments()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [waiting, setWaiting] = useState(false)

  const noReadyDocuments = documents !== null && !documents.some((d) => d.status === "ready")

  async function send(question: string) {
    const history = historyOf(messages)
    setMessages((current) => [...current, { role: "user", content: question }])
    setWaiting(true)
    // The answer is the last message while it streams.
    const updateAnswer = (change: (answer: ChatMessage) => ChatMessage) =>
      setMessages((current) => [...current.slice(0, -1), change(current[current.length - 1])])
    let answering = false
    try {
      await askQuestion(question, history, {
        onSources: (sources) => {
          answering = true
          setMessages((current) => [...current, { role: "assistant", content: "", sources, streaming: true }])
        },
        onText: (text) => updateAnswer((answer) => ({ ...answer, content: answer.content + text })),
      })
      updateAnswer((answer) => ({ ...answer, streaming: false }))
    } catch (e) {
      // A half-written answer is replaced by the error.
      setMessages((current) => [
        ...(answering ? current.slice(0, -1) : current),
        { role: "assistant", content: (e as Error).message, error: true },
      ])
    } finally {
      setWaiting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl">Chat</h1>
        <Button variant="outline" disabled={messages.length === 0} onClick={() => setMessages([])}>
          New chat
        </Button>
      </div>
      {noReadyDocuments && (
        <p className="text-muted-foreground">
          No documents are ready yet. <Link to="/upload" className="text-primary underline">Upload a PDF</Link> to
          start asking questions.
        </p>
      )}
      <MessageList messages={messages} waiting={waiting} />
      <Composer disabled={waiting} onSend={send} />
    </div>
  )
}
