import { Route, Routes } from "react-router-dom"
import { ConversationsProvider } from "@/components/ConversationsProvider"
import { SetupBanner } from "@/components/SetupBanner"
import { Sidebar } from "@/components/Sidebar"
import { useHealth } from "@/hooks/useHealth"
import { ChatPage } from "@/pages/ChatPage"
import { DatabasePage } from "@/pages/DatabasePage"
import { UploadPage } from "@/pages/UploadPage"

export default function App() {
  const { health, error } = useHealth()
  // An unreachable api is itself a setup problem, so it shows up in the same banner.
  const problems = error
    ? [{ code: "api_unreachable", level: "error" as const, message: "The backend is not reachable." }]
    : (health?.problems ?? [])

  // The window never scrolls; each page scrolls its own content.
  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <SetupBanner problems={problems} />
        <main className="min-h-0 flex-1">
          <ConversationsProvider>
            <Routes>
              <Route path="/" element={<ChatPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/database" element={<DatabasePage />} />
            </Routes>
          </ConversationsProvider>
        </main>
      </div>
    </div>
  )
}
