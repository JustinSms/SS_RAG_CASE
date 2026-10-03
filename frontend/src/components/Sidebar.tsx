import { Database, MessageSquare, Upload } from "lucide-react"
import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Chat", icon: MessageSquare },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/database", label: "Database", icon: Database },
]

// Slim icon rail that widens over the page while the pointer (or keyboard focus) is on it.
// The labels stay in the DOM when hidden, so every link keeps its name for screen readers.
const LABEL = "whitespace-nowrap opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100"

export function Sidebar() {
  return (
    // The placeholder keeps the page from moving when the rail widens.
    <div className="relative w-16 shrink-0">
      <aside className="group absolute inset-y-0 left-0 z-40 flex w-16 flex-col overflow-hidden bg-sidebar text-sidebar-foreground transition-[width,box-shadow] duration-200 ease-out hover:w-72 hover:shadow-float focus-within:w-72 focus-within:shadow-float">
        <div className="flex h-16 items-center gap-3 px-3">
          <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white">
            <img src="/stern-stewart-logo.jpg" alt="Stern Stewart logo" className="size-full object-cover" />
          </span>
          <span className={cn(LABEL, "text-sm font-semibold")}>
            Stern Stewart <span className="font-normal text-sidebar-muted">- Document Chat</span>
          </span>
        </div>
        <nav className="mt-4 flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  "relative flex h-10 items-center gap-3 rounded-lg px-2.5 text-sm text-sidebar-muted transition-colors hover:bg-sidebar-hover hover:text-sidebar-foreground",
                  isActive && "bg-sidebar-hover font-medium text-sidebar-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute inset-y-2 -left-3 w-1 rounded-r bg-primary" />}
                  <Icon className={cn("size-5 shrink-0", isActive && "text-primary")} />
                  <span className={LABEL}>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </div>
  )
}
