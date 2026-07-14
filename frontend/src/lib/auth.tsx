import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"

import { isNetworkError, logout, whoami } from "./api"

// Single source of auth truth for the app. Any component reads it via useAuth();
// route guards (RequireAuth) redirect based on it, so the URL always reflects
// the real auth state.
type Status = "loading" | "anon" | "authed"

interface AuthValue {
  status: Status
  user: string | null
  roles: string[]
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthCtx = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const v = useContext(AuthCtx)
  if (!v) throw new Error("useAuth must be used within <AuthProvider>")
  return v
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading")
  const [user, setUser] = useState<string | null>(null)
  const [roles, setRoles] = useState<string[]>([])
  const navigate = useNavigate()
  const statusRef = useRef<Status>("loading")
  statusRef.current = status

  const refresh = useCallback(async () => {
    try {
      const w = await whoami()
      if (w.user === "Guest") {
        // the session really ended (not a network problem) - leave a note
        // for the login screen when it happened mid-work
        if (statusRef.current === "authed")
          sessionStorage.setItem("kamra_session_ended", "1")
        setStatus("anon")
        setUser(null)
        setRoles([])
      } else {
        setStatus("authed")
        setUser(w.full_name || w.user)
        setRoles(w.roles)
      }
    } catch (e) {
      // an unreachable server is NOT a sign-out: keep the session and let
      // the connection banner + screen polling recover on their own
      if (isNetworkError(e)) {
        if (statusRef.current === "loading") setTimeout(refresh, 4000)
        return
      }
      if (statusRef.current === "authed")
        sessionStorage.setItem("kamra_session_ended", "1")
      setStatus("anon")
      setUser(null)
      setRoles([])
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // A stale/expired session surfaces as a 401/403 on some background call. The
  // api layer emits this event; we re-check and, if the session is really gone,
  // drop to anon so RequireAuth redirects to /login instead of leaving a dead
  // screen showing a 403.
  useEffect(() => {
    const onAuthError = () => {
      // only meaningful once we're past the initial load
      if (status !== "loading") refresh()
    }
    window.addEventListener("kamra:auth-error", onAuthError)
    return () => window.removeEventListener("kamra:auth-error", onAuthError)
  }, [refresh, status])

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined)
    setStatus("anon")
    setUser(null)
    setRoles([])
    navigate("/login", { replace: true })
  }, [navigate])

  return (
    <AuthCtx.Provider value={{ status, user, roles, refresh, signOut }}>
      {children}
    </AuthCtx.Provider>
  )
}
