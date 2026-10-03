import { TriangleAlert } from "lucide-react"
import type { Problem } from "@/api/client"

// Shown at the top of every page while /api/health reports problems.
export function SetupBanner({ problems }: { problems: Problem[] }) {
  if (problems.length === 0) return null
  return (
    <div
      role="alert"
      className="mx-4 mt-4 flex items-start gap-3 rounded-xl border border-primary/20 bg-accent px-4 py-3 text-sm text-accent-foreground"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-0.5">
        {problems.map((problem) => (
          <p key={problem.code}>{problem.message}</p>
        ))}
      </div>
    </div>
  )
}
