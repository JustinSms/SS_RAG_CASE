import { useRef, useState } from "react"
import { CloudUpload } from "lucide-react"
import { checkFile, MAX_UPLOAD_MB } from "@/lib/upload"
import { cn } from "@/lib/utils"

type Props = { onUpload: (files: File[]) => Promise<void> }

// Click or drag PDFs in. Files the backend would refuse are rejected here first.
export function Dropzone({ onUpload }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [messages, setMessages] = useState<string[]>([])

  async function handle(picked: FileList | null) {
    const files = Array.from(picked ?? [])
    const problems = files.map(checkFile)
    const accepted = files.filter((_, i) => problems[i] === null)
    const rejected = problems.filter((p): p is string => p !== null)
    if (accepted.length > 0) {
      try {
        await onUpload(accepted)
      } catch (e) {
        rejected.push((e as Error).message)
      }
    }
    setMessages(rejected)
    // Lets the same file be picked again after it was rejected or deleted.
    if (input.current) input.current.value = ""
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload PDFs"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => (e.preventDefault(), setDragging(true))}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handle(e.dataTransfer.files)
        }}
        className={cn(
          "group flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-input bg-background px-6 py-14 text-center shadow-card transition-all hover:border-primary/50 hover:bg-accent/40 focus-visible:outline-2",
          dragging && "scale-[1.01] border-primary bg-accent",
        )}
      >
        <span
          className={cn(
            "flex size-14 items-center justify-center rounded-2xl bg-accent text-primary transition-transform group-hover:-translate-y-0.5",
            dragging && "bg-primary text-primary-foreground",
          )}
        >
          <CloudUpload className="size-7" />
        </span>
        <p className="text-base font-medium text-card-foreground">
          Drop PDFs here or <span className="text-primary">click to choose</span>
        </p>
        <p className="text-xs text-muted-foreground">PDF only, up to {MAX_UPLOAD_MB} MB each</p>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          data-testid="file-input"
          onChange={(e) => handle(e.target.files)}
        />
      </div>
      {messages.length > 0 && (
        <ul role="alert" className="mt-3 space-y-1 rounded-xl border border-primary/20 bg-accent px-4 py-3 text-sm text-accent-foreground">
          {messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
