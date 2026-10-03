import type { DocumentStatus } from "@/api/client"
import { Badge } from "@/components/ui/badge"

const VARIANT = { processing: "secondary", ready: "success", failed: "default" } as const

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <Badge variant={VARIANT[status]}>{status}</Badge>
}
