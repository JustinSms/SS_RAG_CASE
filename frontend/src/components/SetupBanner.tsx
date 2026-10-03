import type { Problem } from "@/api/client"

// Red banner below the top bar, shown on every page while /api/health reports problems.
export function SetupBanner({ problems }: { problems: Problem[] }) {
  if (problems.length === 0) return null
  return (
    <div role="alert" className="bg-primary px-6 py-2 text-sm text-primary-foreground">
      {problems.map((problem) => (
        <p key={problem.code}>{problem.message}</p>
      ))}
    </div>
  )
}
