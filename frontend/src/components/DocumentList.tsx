import { Trash2 } from "lucide-react"
import type { Document } from "@/api/client"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"

type Props = { documents: Document[]; onDelete: (document: Document) => void }

export function DocumentList({ documents, onDelete }: Props) {
  if (documents.length === 0) {
    return <p className="text-sm text-muted-foreground">No documents yet.</p>
  }
  return (
    <ul className="divide-y rounded-md border">
      {documents.map((document) => (
        <li key={document.id} className="flex items-center gap-4 p-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{document.filename}</p>
            {document.status === "failed" && document.error && (
              <p className="text-sm text-destructive">{document.error}</p>
            )}
          </div>
          <span className="w-20 text-sm text-muted-foreground">
            {document.page_count === null ? "" : `${document.page_count} pages`}
          </span>
          <StatusBadge status={document.status} />
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Delete ${document.filename}`}
            onClick={() => onDelete(document)}
          >
            <Trash2 />
          </Button>
        </li>
      ))}
    </ul>
  )
}
