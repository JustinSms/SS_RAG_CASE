import type { DocumentStatus } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const VARIANT = { processing: "secondary", ready: "success", failed: "default" } as const
const DOT = { processing: "bg-muted-foreground animate-pulse", ready: "bg-success", failed: "bg-primary" }

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge variant={VARIANT[status]}>
      <span className={cn("size-1.5 rounded-full", DOT[status])} aria-hidden />
      {status}
    </Badge>
  )
}
