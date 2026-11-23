import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import "./index.css"
import App from "./App"
import { initTheme } from "./lib/theme"
import { initLang } from "./lib/dir"
import { asset } from "./lib/asset"
import { AuthProvider } from "./lib/auth"
import { CashierAuthProvider } from "./lib/cashierAuth"
import { ROUTER_BASENAME } from "./lib/routing"

initTheme()

// Favicons, base-aware (see index.html note).
function setIcon(rel: string, href: string, type?: string) {
  const link = document.createElement("link")
  link.rel = rel
  link.href = asset(href)
  if (type) link.type = type
  document.head.appendChild(link)
}
setIcon("icon", "kamra-mark.svg", "image/svg+xml")
setIcon("icon", "favicon-32.png", "image/png")
setIcon("apple-touch-icon", "apple-touch-180.png")

// Offline (#228): the service worker keeps the app shell and built files
// (kamra/www/kamra-sw.min.js, served at the site root so it may control
// /kamra). Production only; the dev server has no /kamra.
function registerServiceWorker() {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return
  if (!location.pathname.startsWith("/kamra")) return
  navigator.serviceWorker.register("/kamra-sw.min.js", { scope: "/kamra" })
    .then(() => navigator.serviceWorker.ready)
    .then((reg) => {
      const loaded = performance.getEntriesByType("resource").map((e) => e.name)
      reg.active?.postMessage({ cache: loaded })
    })
    .catch(() => undefined) // offline support is a bonus, never a blocker
}
registerServiceWorker()

function mount() {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter basename={ROUTER_BASENAME}>
        <AuthProvider>
          <CashierAuthProvider>
            <App />
          </CashierAuthProvider>
        </AuthProvider>
      </BrowserRouter>
    </StrictMode>,
  )
}

// Wait for the active locale chunk so the first paint is already
// translated; English skips the network round-trip.
void initLang().then(mount)
