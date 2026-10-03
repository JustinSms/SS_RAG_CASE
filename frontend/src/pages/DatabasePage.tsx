import { useState } from "react"
import { listChunks, listSections, type Document, type Section } from "@/api/client"
import { ChunkTable } from "@/components/ChunkTable"
import { SectionTree } from "@/components/SectionTree"
import { StatusBadge } from "@/components/StatusBadge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDocuments } from "@/hooks/useDocuments"
import { useFetched } from "@/hooks/useFetched"
import { cn } from "@/lib/utils"

const BYTES_PER_KB = 1024
const BYTES_PER_MB = BYTES_PER_KB * 1024

function formatSize(bytes: number): string {
  return bytes >= BYTES_PER_MB
    ? `${(bytes / BYTES_PER_MB).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / BYTES_PER_KB))} KB`
}

function Problem({ message }: { message: string }) {
  return <p className="text-sm text-destructive">{message}</p>
}

// Read-only: documents -> sections -> chunks. Deleting is only possible on the Upload page.
export function DatabasePage() {
  const { documents, error } = useDocuments()
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [section, setSection] = useState<Section | null>(null)

  const document = documents?.find((d) => d.id === documentId)
  const sections = useFetched(documentId, listSections)
  const chunks = useFetched(section?.id ?? null, listChunks)

  function selectDocument(selected: Document) {
    setDocumentId(selected.id)
    setSection(null)
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-2xl">Database</h1>
        {error && <Problem message={error} />}
        {documents?.length === 0 && (
          <p className="text-sm text-muted-foreground">No documents yet.</p>
        )}
        {documents && documents.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Pages</TableHead>
                <TableHead>Sections</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Uploaded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((d) => (
                <TableRow
                  key={d.id}
                  data-state={d.id === documentId ? "selected" : undefined}
                  className={cn("cursor-pointer hover:bg-accent", d.id === documentId && "font-medium")}
                  onClick={() => selectDocument(d)}
                >
                  <TableCell>
                    {/* The click is handled by the row; the button makes it reachable with the keyboard. */}
                    <button type="button" className="text-left">
                      {d.filename}
                    </button>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} />
                  </TableCell>
                  <TableCell>{d.page_count ?? ""}</TableCell>
                  <TableCell>{d.section_count}</TableCell>
                  <TableCell>{d.chunk_count ?? ""}</TableCell>
                  <TableCell>{formatSize(d.size_bytes)}</TableCell>
                  <TableCell>{new Date(d.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      {document && (
        <section className="space-y-3">
          <h2 className="text-xl">Sections of {document.filename}</h2>
          {sections.error && <Problem message={sections.error} />}
          {sections.data && (
            <SectionTree sections={sections.data} selectedId={section?.id ?? null} onSelect={setSection} />
          )}
        </section>
      )}

      {section && (
        <section className="space-y-3">
          <h2 className="text-xl">Chunks of {section.heading}</h2>
          {chunks.error && <Problem message={chunks.error} />}
          {chunks.data && <ChunkTable chunks={chunks.data} />}
        </section>
      )}
    </div>
  )
}
