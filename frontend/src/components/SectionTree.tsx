import type { Section } from "@/api/client"
import { formatPages } from "@/lib/pages"
import { cn } from "@/lib/utils"

type Props = { sections: Section[]; selectedId: string | null; onSelect: (section: Section) => void }

// The api sends sections in document order with their level, so indenting by level draws the tree.
export function SectionTree({ sections, selectedId, onSelect }: Props) {
  if (sections.length === 0) return <p className="text-sm text-muted-foreground">No sections.</p>
  return (
    <ul className="divide-y rounded-md border">
      {sections.map((section) => (
        <li key={section.id}>
          <button
            type="button"
            onClick={() => onSelect(section)}
            aria-current={section.id === selectedId}
            className={cn(
              "flex w-full items-baseline gap-4 py-2 pr-3 text-left text-sm hover:bg-accent",
              section.id === selectedId && "bg-accent font-medium",
            )}
            style={{ paddingLeft: `${section.level}rem` }}
          >
            <span className="min-w-0 flex-1 truncate">{section.heading}</span>
            <span className="text-muted-foreground">
              {formatPages(section.page_start, section.page_end)}
            </span>
            <span className="w-24 text-right text-muted-foreground">
              {section.chunk_count} {section.chunk_count === 1 ? "chunk" : "chunks"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
