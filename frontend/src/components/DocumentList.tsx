import { FileText, Trash2 } from "lucide-react"
import type { Document } from "@/api/client"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

type Props = { documents: Document[]; onDelete: (document: Document) => void }

// The chunk count is only known once the document is split; until then the bar stays empty.
function percentDone(document: Document): number {
  if (!document.chunk_count) return 0
  return Math.round((document.chunks_done / document.chunk_count) * 100)
}

export function DocumentList({ documents, onDelete }: Props) {
  if (documents.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed bg-background px-6 py-10 text-center text-sm text-muted-foreground">
        No documents yet.
      </p>
    )
  }
  return (
    <ul className="divide-y overflow-hidden rounded-2xl border bg-background shadow-card">
      {documents.map((document) => (
        <li key={document.id} className="group flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-muted/60">
          <span
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-muted-foreground",
              document.status === "failed" && "bg-accent text-primary",
            )}
          >
            <FileText className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-card-foreground">{document.filename}</p>
            {document.status === "failed" && document.error && (
              <p className="text-sm text-destructive">{document.error}</p>
            )}
            {document.status === "processing" && (
              <Progress
                className="mt-2 h-1.5"
                aria-label={`Processing ${document.filename}`}
                value={percentDone(document)}
              />
            )}
          </div>
          <span className="w-20 text-right text-sm text-muted-foreground">
            {document.page_count === null ? "" : `${document.page_count} pages`}
          </span>
          <StatusBadge status={document.status} />
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Delete ${document.filename}`}
            onClick={() => onDelete(document)}
            className="text-muted-foreground hover:text-primary"
          >
            <Trash2 />
          </Button>
        </li>
      ))}
    </ul>
  )
}
