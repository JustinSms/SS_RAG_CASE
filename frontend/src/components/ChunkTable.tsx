import type { Chunk } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatPages } from "@/lib/pages"

const EMPTY = <span className="text-muted-foreground">-</span>

// The embedding vector is not shown, only whether it is stored.
export function ChunkTable({ chunks }: { chunks: Chunk[] }) {
  if (chunks.length === 0) return <p className="text-sm text-muted-foreground">No chunks.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>#</TableHead>
          <TableHead>Pages</TableHead>
          <TableHead>Text</TableHead>
          <TableHead>Context</TableHead>
          <TableHead>Summary</TableHead>
          <TableHead>Keywords</TableHead>
          <TableHead>Enrichment</TableHead>
          <TableHead>Embedding</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {chunks.map((chunk) => (
          <TableRow key={chunk.id}>
            <TableCell>{chunk.position_in_section + 1}</TableCell>
            <TableCell className="whitespace-nowrap">
              {formatPages(chunk.page_start, chunk.page_end)}
            </TableCell>
            <TableCell className="min-w-72 whitespace-pre-wrap">{chunk.text}</TableCell>
            <TableCell className="min-w-48">{chunk.context ?? EMPTY}</TableCell>
            <TableCell className="min-w-48">{chunk.summary ?? EMPTY}</TableCell>
            <TableCell className="min-w-32">
              {chunk.keywords?.length ? chunk.keywords.join(", ") : EMPTY}
            </TableCell>
            <TableCell>
              {chunk.enriched ? "enriched" : <Badge variant="outline">not enriched</Badge>}
            </TableCell>
            <TableCell>{chunk.has_embedding ? "yes" : "no"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
