import { useState } from "react"
import { Button } from "@/components/ui/button"

type Props = { disabled: boolean; onSend: (question: string) => void }

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState("")

  function submit() {
    const question = text.trim()
    if (!question || disabled) return
    setText("")
    onSend(question)
  }

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault()
            submit()
          }
        }}
        rows={2}
        placeholder="Ask a question about your documents"
        aria-label="Question"
        className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 focus-visible:outline-2"
      />
      <Button type="submit" disabled={disabled || !text.trim()}>
        Send
      </Button>
    </form>
  )
}
