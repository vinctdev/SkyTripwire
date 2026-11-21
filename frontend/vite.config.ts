import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The backend (FastAPI) listens on 127.0.0.1:8000 by default. In development Vite serves the
// UI and forwards /api to it, in production the backend serves the built files itself.
const backend = process.env.SKYTRIPWIRE_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Bundled dependencies (React, Leaflet, ...) require their license notices in every copy.
  // Plain text so browsers show it instead of downloading it; the backend serves it at
  // /third-party-licenses.txt and the footer links to it.
  build: { license: { fileName: "third-party-licenses.txt" } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": backend },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
