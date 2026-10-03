import { useState } from "react"
import { ArrowUp } from "lucide-react"
import { Button } from "@/components/ui/button"

type Props = { disabled: boolean; onSend: (question: string) => void }

// The textarea grows with its text up to this height, then scrolls.
const MAX_HEIGHT_PX = 200

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
      className="flex items-end gap-2 rounded-2xl border bg-background p-2 shadow-float transition-colors focus-within:border-primary/40"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onInput={(event) => {
          const area = event.currentTarget
          area.style.height = "auto"
          area.style.height = `${Math.min(area.scrollHeight, MAX_HEIGHT_PX)}px`
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault()
            submit()
          }
        }}
        rows={1}
        placeholder="Ask a question about your documents"
        aria-label="Question"
        className="max-h-[200px] flex-1 resize-none bg-transparent px-3 py-2 outline-none placeholder:text-muted-foreground"
      />
      <Button type="submit" size="icon" aria-label="Send" className="rounded-xl" disabled={disabled || !text.trim()}>
        <ArrowUp className="size-5" />
      </Button>
    </form>
  )
}
