import { FileText } from "lucide-react"
import type { Source } from "@/api/client"
import { formatPages } from "@/lib/pages"

const SCORE_DECIMALS = 2

// The number on the chip: the rerank score, or the cosine score if the reranker failed.
// A chunk added by section selection was not scored. Old saved chats have no scores at all.
export function scoreBadge(source: Source): { text: string; title: string } | null {
  if (source.rerank != null) {
    const cosine = source.cosine != null ? `, cosine similarity ${source.cosine.toFixed(SCORE_DECIMALS)}` : ""
    return { text: source.rerank.toFixed(SCORE_DECIMALS), title: `Rerank score ${source.rerank.toFixed(SCORE_DECIMALS)}${cosine}` }
  }
  if (source.cosine != null) {
    const cosine = source.cosine.toFixed(SCORE_DECIMALS)
    return { text: `cos ${cosine}`, title: `Cosine similarity ${cosine} (reranker unavailable)` }
  }
  if (source.cosine === null) return { text: "added", title: "Added by section selection (not scored)" }
  return null
}

// The text comes from the stored source, never from the model, so it cannot be invented.
export function CitationChip({ source }: { source: Source }) {
  const label = `[${source.filename}, ${formatPages(source.page_start, source.page_end)}, ${source.heading_path}]`
  const score = scoreBadge(source)
  return (
    <a
      title={score ? `${label}\n${score.title}` : label}
      href={`/api/documents/${source.document_id}/file#page=${source.page_start}`}
      target="_blank"
      rel="noreferrer"
      className="group mx-0.5 inline-flex max-w-full items-center gap-1 rounded-full border border-primary/15 bg-accent px-2 py-0.5 align-baseline text-xs font-medium text-accent-foreground transition-colors hover:border-primary/40 hover:bg-primary hover:text-primary-foreground"
    >
      <FileText className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{label}</span>
      {score && (
        <span
          aria-label={score.title}
          className="shrink-0 rounded-full bg-primary/10 px-1.5 font-semibold tabular-nums group-hover:bg-primary-foreground/20"
        >
          {score.text}
        </span>
      )}
    </a>
  )
}
