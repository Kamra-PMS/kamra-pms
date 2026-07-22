import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

// Dev (`vite`): served at / on :5173, proxying /api to the Frappe bench.
// Build (`vite build`): emits into the Frappe app's public/ folder, which
// Frappe serves at /assets/kamra/frontend/. The served SPA mounts at /kamra
// (see the router basename in main.tsx and website_route_rules in hooks.py).
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/assets/kamra/frontend/" : "/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../kamra/public/frontend",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    // Defaults preserved; override with env when the standard ports are taken
    // (e.g. KAMRA_DEV_PORT=5174 KAMRA_API_TARGET=http://localhost:8080).
    port: Number(process.env.KAMRA_DEV_PORT) || 5173,
    proxy: {
      "/api": {
        target: process.env.KAMRA_API_TARGET || "http://localhost:8000",
        headers: { Host: "kamra.localhost" },
      },
    },
  },
}))
