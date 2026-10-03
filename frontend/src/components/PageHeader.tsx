import type { ReactNode } from "react"

type Props = { title: string; description: string; children?: ReactNode }

// Title row of the Upload and Database pages; `children` go to the right (counts, actions).
export function PageHeader({ title, description, children }: Props) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="space-y-1">
        <h1 className="text-3xl">{title}</h1>
        <p className="text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  )
}
