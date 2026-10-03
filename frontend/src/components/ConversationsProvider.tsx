import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import type { ChatMessage } from "@/components/MessageList"

export const CONVERSATIONS_KEY = "document-chat.conversations"
export const ACTIVE_KEY = "document-chat.active"
// Only the newest chats are kept; starting one more drops the oldest.
export const MAX_SAVED_CHATS = 10
const TITLE_LENGTH = 60

export type Conversation = {
  id: string
  title: string
  updatedAt: string
  messages: ChatMessage[]
}

// A stored answer that was still streaming when the page closed is shown as finished.
function load(): Conversation[] {
  try {
    const stored: Conversation[] = JSON.parse(localStorage.getItem(CONVERSATIONS_KEY) ?? "[]")
    return stored
      .slice(0, MAX_SAVED_CHATS)
      .map((c) => ({ ...c, messages: c.messages.map((m) => ({ ...m, streaming: false })) }))
  } catch {
    return []
  }
}

function useConversationState() {
  const [conversations, setConversations] = useState<Conversation[]>(load)
  // null is a new chat that has no question yet.
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem(ACTIVE_KEY))
  // The conversation whose answer is on its way.
  const [waitingId, setWaitingId] = useState<string | null>(null)

  useEffect(() => {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations))
  }, [conversations])

  useEffect(() => {
    if (activeId === null) localStorage.removeItem(ACTIVE_KEY)
    else localStorage.setItem(ACTIVE_KEY, activeId)
  }, [activeId])

  // Starts a conversation titled after its first question and returns its id.
  const create = useCallback((question: string) => {
    const id = crypto.randomUUID()
    const title = question.length > TITLE_LENGTH ? `${question.slice(0, TITLE_LENGTH)}...` : question
    const conversation = { id, title, updatedAt: new Date().toISOString(), messages: [] }
    setConversations((current) => [conversation, ...current].slice(0, MAX_SAVED_CHATS))
    return id
  }, [])

  const update = useCallback((id: string, change: (messages: ChatMessage[]) => ChatMessage[]) => {
    setConversations((current) => {
      const conversation = current.find((c) => c.id === id)
      if (!conversation) return current
      const changed = { ...conversation, messages: change(conversation.messages), updatedAt: new Date().toISOString() }
      return [changed, ...current.filter((c) => c.id !== id)]
    })
  }, [])

  const remove = useCallback((id: string) => {
    setConversations((current) => current.filter((c) => c.id !== id))
    setActiveId((current) => (current === id ? null : current))
  }, [])

  // An active id whose chat no longer exists (deleted, or dropped as the oldest) is a new chat.
  const active = conversations.find((c) => c.id === activeId) ?? null

  return { conversations, active, setActiveId, waitingId, setWaitingId, create, update, remove }
}

const ConversationsContext = createContext<ReturnType<typeof useConversationState> | null>(null)

// Old chats live in the browser only (the api keeps no conversations), newest first. The state sits
// above the routes, so the open chat and an answer that is still streaming survive a page change.
export function ConversationsProvider({ children }: { children: ReactNode }) {
  return <ConversationsContext value={useConversationState()}>{children}</ConversationsContext>
}

export function useConversations() {
  const value = useContext(ConversationsContext)
  if (!value) throw new Error("useConversations needs a ConversationsProvider")
  return value
}
