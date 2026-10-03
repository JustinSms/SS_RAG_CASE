/// <reference types="vitest/config" />
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  // `npm run dev` talks to the api container started by compose on port 8000.
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.ts" },
})
