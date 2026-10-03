import type { ReactNode } from "react"
import { Check, X } from "lucide-react"
import type { Chunk } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { formatPages } from "@/lib/pages"

const EMPTY = <span className="text-muted-foreground">-</span>

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

// One card per chunk. The embedding vector is not shown, only whether it is stored.
export function ChunkList({ chunks }: { chunks: Chunk[] }) {
  if (chunks.length === 0) return <p className="text-sm text-muted-foreground">No chunks.</p>
  return (
    <ul className="space-y-3">
      {chunks.map((chunk) => (
        <li key={chunk.id} className="space-y-3 rounded-2xl border bg-background p-4 shadow-card">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="flex size-6 items-center justify-center rounded-md bg-secondary font-semibold">
              {chunk.position_in_section + 1}
            </span>
            <Badge variant="outline">{formatPages(chunk.page_start, chunk.page_end)}</Badge>
            {chunk.enriched ? <Badge variant="success">enriched</Badge> : <Badge>not enriched</Badge>}
            <span className="ml-auto flex items-center gap-1 text-muted-foreground">
              {chunk.has_embedding ? <Check className="size-3.5 text-success" /> : <X className="size-3.5 text-primary" />}
              Embedding: <span className="font-medium text-foreground">{chunk.has_embedding ? "yes" : "no"}</span>
            </span>
          </div>
          <p className="rounded-xl bg-muted px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">{chunk.text}</p>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Field label="Context">{chunk.context ?? EMPTY}</Field>
            <Field label="Summary">{chunk.summary ?? EMPTY}</Field>
            <Field label="Keywords">{chunk.keywords?.length ? chunk.keywords.join(", ") : EMPTY}</Field>
          </dl>
        </li>
      ))}
    </ul>
  )
}
