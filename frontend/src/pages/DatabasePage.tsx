import { useState } from "react"
import { FileText, ListTree, Rows3 } from "lucide-react"
import { listChunks, listSections, type Document, type Section } from "@/api/client"
import { ChunkList } from "@/components/ChunkList"
import { PageHeader } from "@/components/PageHeader"
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

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-background px-4 py-2 shadow-card">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold text-card-foreground">{value}</p>
    </div>
  )
}

function Hint({ children }: { children: string }) {
  return (
    <p className="rounded-2xl border border-dashed bg-background px-6 py-10 text-center text-sm text-muted-foreground">
      {children}
    </p>
  )
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

  const total = (count: (d: Document) => number) => documents?.reduce((sum, d) => sum + count(d), 0) ?? 0

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl space-y-8 px-8 py-10">
        <PageHeader title="Database" description="What the pipeline stored: documents, their sections and the chunks in each.">
          {documents && documents.length > 0 && (
            <div className="flex gap-3">
              <Stat label="Documents" value={documents.length} />
              <Stat label="Sections" value={total((d) => d.section_count)} />
              <Stat label="Chunks" value={total((d) => d.chunk_count ?? 0)} />
            </div>
          )}
        </PageHeader>

        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-lg">
            <FileText className="size-5 text-primary" /> Documents
          </h2>
          {error && <Problem message={error} />}
          {documents?.length === 0 && <Hint>No documents yet.</Hint>}
          {documents && documents.length > 0 && (
            <div className="overflow-hidden rounded-2xl border bg-background shadow-card">
              <Table>
                <TableHeader className="bg-muted/60">
                  <TableRow>
                    <TableHead className="px-4">File</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Pages</TableHead>
                    <TableHead>Sections</TableHead>
                    <TableHead>Chunks</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead className="px-4">Uploaded</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((d) => (
                    <TableRow
                      key={d.id}
                      data-state={d.id === documentId ? "selected" : undefined}
                      className={cn(
                        "cursor-pointer hover:bg-muted/60 data-[state=selected]:bg-accent",
                        d.id === documentId && "font-medium",
                      )}
                      onClick={() => selectDocument(d)}
                    >
                      <TableCell className="px-4 py-3 align-middle">
                        {/* The click is handled by the row; the button makes it reachable with the keyboard. */}
                        <button type="button" className="text-left">
                          {d.filename}
                        </button>
                      </TableCell>
                      <TableCell className="align-middle">
                        <StatusBadge status={d.status} />
                      </TableCell>
                      <TableCell className="align-middle">{d.page_count ?? ""}</TableCell>
                      <TableCell className="align-middle">{d.section_count}</TableCell>
                      <TableCell className="align-middle">{d.chunk_count ?? ""}</TableCell>
                      <TableCell className="align-middle text-muted-foreground">{formatSize(d.size_bytes)}</TableCell>
                      <TableCell className="px-4 align-middle text-muted-foreground">
                        {new Date(d.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </section>

        {document && (
          <div className="grid items-start gap-6 lg:grid-cols-[24rem_1fr]">
            <section className="space-y-3 lg:sticky lg:top-0">
              <h2 className="flex items-center gap-2 text-lg">
                <ListTree className="size-5 text-primary" />
                <span className="truncate">Sections of {document.filename}</span>
              </h2>
              {sections.error && <Problem message={sections.error} />}
              {sections.data && (
                <div className="max-h-[70vh] overflow-y-auto rounded-2xl border bg-background shadow-card">
                  <SectionTree sections={sections.data} selectedId={section?.id ?? null} onSelect={setSection} />
                </div>
              )}
            </section>

            <section className="min-w-0 space-y-3">
              {section ? (
                <>
                  <h2 className="flex items-center gap-2 text-lg">
                    <Rows3 className="size-5 text-primary" />
                    <span className="truncate">Chunks of {section.heading}</span>
                  </h2>
                  {chunks.error && <Problem message={chunks.error} />}
                  {chunks.data && <ChunkList chunks={chunks.data} />}
                </>
              ) : (
                <Hint>Choose a section to see its chunks.</Hint>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
