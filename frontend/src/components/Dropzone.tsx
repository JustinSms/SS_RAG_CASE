import { useRef, useState } from "react"
import { Upload } from "lucide-react"
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
          "flex cursor-pointer flex-col items-center gap-2 rounded-md border-2 border-dashed p-10 text-center text-sm text-muted-foreground transition-colors hover:bg-accent",
          dragging && "border-primary bg-accent",
        )}
      >
        <Upload className="size-6" />
        <p>Drop PDFs here or click to choose</p>
        <p className="text-xs">PDF only, up to {MAX_UPLOAD_MB} MB each</p>
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
        <ul role="alert" className="mt-3 space-y-1 text-sm text-destructive">
          {messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
