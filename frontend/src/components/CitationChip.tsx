import { FileText } from "lucide-react"
import type { Source } from "@/api/client"
import { formatPages } from "@/lib/pages"

// The text comes from the stored source, never from the model, so it cannot be invented.
export function CitationChip({ source }: { source: Source }) {
  const label = `[${source.filename}, ${formatPages(source.page_start, source.page_end)}, ${source.heading_path}]`
  return (
    <a
      title={label}
      href={`/api/documents/${source.document_id}/file#page=${source.page_start}`}
      target="_blank"
      rel="noreferrer"
      className="mx-0.5 inline-flex max-w-full items-center gap-1 rounded-full border border-primary/15 bg-accent px-2 py-0.5 align-baseline text-xs font-medium text-accent-foreground transition-colors hover:border-primary/40 hover:bg-primary hover:text-primary-foreground"
    >
      <FileText className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{label}</span>
    </a>
  )
}
