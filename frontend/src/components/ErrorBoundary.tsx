import { Component, type ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import { RefreshCw } from "lucide-react"
import { Button } from "./ui/button"
import { t } from "../lib/i18n"

// Pages anyone can open without a staff login: no desk links there.
const PUBLIC_PREFIXES = ["/book", "/stay", "/checkin", "/hk", "/login"]

/** True when a lazy screen's JS chunk failed to load: offline, or a deploy
 *  replaced the hashed file this tab still points at. */
export function isChunkError(e: unknown): boolean {
  const msg = String((e as Error)?.message ?? "")
  return (
    (e as Error)?.name === "ChunkLoadError" ||
    /dynamically imported module|Importing a module script failed|error loading dynamically|Loading (CSS )?chunk/i.test(
      msg,
    )
  )
}

const RELOAD_KEY = "kamra_chunk_reload_at"

/** Reload once to pick up the new build. Guarded so a chunk that is truly
 *  gone (or a dead connection) never loops: at most one auto-reload a minute. */
function reloadForNewBuild(): boolean {
  if (!navigator.onLine) return false
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0)
    if (Date.now() - last < 60_000) return false
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  } catch {
    return false
  }
  location.reload()
  return true
}

type Props = { children: ReactNode; resetKey: string; staff: boolean }

class Boundary extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    // the details are for us, never for the guest or the desk
    console.error("[kamra] screen crashed", error, info.componentStack)
    if (isChunkError(error)) reloadForNewBuild()
  }

  componentDidUpdate(prev: Props) {
    // navigating away recovers: the next screen gets a clean slate
    if (prev.resetKey !== this.props.resetKey && this.state.error)
      this.setState({ error: null })
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    const chunk = isChunkError(error)
    const offline = !navigator.onLine
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center" role="alert">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-brand-50 text-brand-700">
          <RefreshCw className="size-5" aria-hidden />
        </div>
        <h2 className="text-lg font-semibold text-zinc-900">
          {offline
            ? t("You're offline")
            : chunk
              ? t("A new version is ready")
              : t("This page hit a problem")}
        </h2>
        <p className="mt-2 text-sm text-zinc-600">
          {offline
            ? t("Check your connection, then try again.")
            : chunk
              ? t("Reload to get the latest version of this page.")
              : t("Try again, or reload the page if it keeps happening.")}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {/* a lazy chunk that failed stays failed until a reload */}
          {!chunk && (
            <Button onClick={() => this.setState({ error: null })}>
              {t("Try again")}
            </Button>
          )}
          <Button variant={chunk ? "primary" : "outline"} onClick={() => location.reload()}>
            {t("Reload")}
          </Button>
          {this.props.staff && (
            <Link
              to="/"
              onClick={() => this.setState({ error: null })}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-brand-700 hover:bg-brand-50"
            >
              {t("Go to Today")}
            </Link>
          )}
        </div>
      </div>
    )
  }
}

/** Friendly crash panel that resets on navigation. Wrap the whole app and
 *  each screen outlet, so one broken screen keeps the nav usable. */
export default function ErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const staff = !PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"))
  return (
    <Boundary resetKey={pathname} staff={staff}>
      {children}
    </Boundary>
  )
}
