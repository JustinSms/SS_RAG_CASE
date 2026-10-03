import type { Source } from "@/api/client"

function pages(source: Source): string {
  return source.page_start === source.page_end
    ? `p. ${source.page_start}`
    : `p. ${source.page_start}-${source.page_end}`
}

// The text comes from the stored source, never from the model, so it cannot be invented.
export function CitationChip({ source }: { source: Source }) {
  return (
    <a
      href={`/api/documents/${source.document_id}/file#page=${source.page_start}`}
      target="_blank"
      rel="noreferrer"
      className="mx-0.5 inline-block rounded-sm bg-accent px-1.5 py-0.5 align-baseline text-xs text-accent-foreground hover:underline"
    >
      [{source.filename}, {pages(source)}, {source.heading_path}]
    </a>
  )
}
