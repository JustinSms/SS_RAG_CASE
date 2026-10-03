import { NavLink, Route, Routes } from "react-router-dom"
import { SetupBanner } from "@/components/SetupBanner"
import { useHealth } from "@/hooks/useHealth"
import { cn } from "@/lib/utils"
import { ChatPage } from "@/pages/ChatPage"
import { DatabasePage } from "@/pages/DatabasePage"
import { UploadPage } from "@/pages/UploadPage"

const NAV = [
  { to: "/", label: "Chat" },
  { to: "/upload", label: "Upload" },
  { to: "/database", label: "Database" },
]

export default function App() {
  const { health, error } = useHealth()
  // An unreachable api is itself a setup problem, so it shows up in the same banner.
  const problems = error
    ? [{ code: "api_unreachable", level: "error" as const, message: "The backend is not reachable." }]
    : (health?.problems ?? [])

  return (
    <div className="min-h-screen">
      <header className="flex h-14 items-center gap-8 bg-header px-6 text-header-foreground">
        <span className="text-lg font-bold">Document Chat</span>
        <nav className="flex h-full gap-6">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  "flex h-full items-center border-b-2 border-transparent text-sm",
                  isActive && "border-primary font-bold",
                )
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <SetupBanner problems={problems} />
      <main className="mx-auto max-w-5xl p-6">
        <Routes>
          <Route path="/" element={<ChatPage health={health} error={error} />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/database" element={<DatabasePage />} />
        </Routes>
      </main>
    </div>
  )
}
