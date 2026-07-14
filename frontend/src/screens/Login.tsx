import { useEffect, useState } from "react"

import { call, login } from "../lib/api"
import { asset } from "../lib/asset"
import { Button } from "../components/ui/button"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const DEMO_ACCOUNTS = [
  { label: "System Admin", usr: "admin@kamra.local", pwd: "KamraAdmin1!" },
  { label: "Hotel Admin (GM)", usr: "gm@kamra.local", pwd: "KamraGM1!" },
  { label: "Front Desk", usr: "frontdesk@kamra.local", pwd: "KamraDesk1!" },
  { label: "Revenue", usr: "revenue@kamra.local", pwd: "KamraRev1!" },
  { label: "Finance", usr: "finance@kamra.local", pwd: "KamraFin1!" },
  { label: "Housekeeping", usr: "hk@kamra.local", pwd: "KamraHK1!" },
]

export default function Login(props: { onSuccess: () => void }) {
  const [usr, setUsr] = useState("")
  const [pwd, setPwd] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Demo accounts only exist on the seeded demo site; hide them elsewhere.
  const [demoMode, setDemoMode] = useState(false)

  useEffect(() => {
    call<{ demo_mode: boolean }>("kamra.public_api.site_info")
      .then((info) => setDemoMode(info.demo_mode))
      .catch(() => setDemoMode(false))
  }, [])

  async function submit(u = usr, p = pwd) {
    setBusy(true)
    setError(null)
    try {
      await login(u, p)
      // Navigation + the production CSRF re-boot are handled by the /login
      // route (LoginPage.onSuccess).
      sessionStorage.removeItem("kamra_session_ended")
      props.onSuccess()
    } catch {
      setError("Wrong email or password.")
    } finally {
      setBusy(false)
    }
  }

  const sessionEnded = sessionStorage.getItem("kamra_session_ended") === "1"

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
      <div className="w-full max-w-sm">
        {sessionEnded && (
          <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-center text-sm text-amber-800">
            Your session ended — sign in to pick up where you left off.
          </p>
        )}
        <div className="mb-6 flex flex-col items-center gap-2">
          <img src={asset("kamra-mark.svg")} alt="Kamra" className="size-16" />
          <span className="text-2xl font-semibold tracking-tight">
            kamra
            <span className="ml-1.5 align-middle text-xs font-semibold tracking-[0.25em] text-brand-600">
              PMS
            </span>
          </span>
        </div>

        <form
          className="space-y-3 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600">
              Email
            </span>
            <input
              className={inputCls}
              type="email"
              autoComplete="username"
              value={usr}
              onChange={(e) => setUsr(e.target.value)}
              placeholder="you@hotel.com"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-600">
              Password
            </span>
            <input
              className={inputCls}
              type="password"
              autoComplete="current-password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
            />
          </label>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}

          <Button
            className="w-full justify-center py-2"
            disabled={busy || !usr || !pwd}
            type="submit"
          >
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        {demoMode && (
        <div className="mt-4 rounded-xl border border-dashed border-zinc-300 p-4">
          <p className="mb-2 text-center text-xs text-zinc-400">
            Demo accounts - one tap to try each role
          </p>
          <div className="grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.usr}
                disabled={busy}
                onClick={() => submit(a.usr, a.pwd)}
                className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs font-medium text-zinc-600 hover:border-brand-600 hover:text-brand-700"
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>
        )}
      </div>
    </div>
  )
}
