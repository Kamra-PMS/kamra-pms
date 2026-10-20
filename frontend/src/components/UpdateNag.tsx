import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowUpCircle, X } from "lucide-react"
import { call } from "../lib/api"
import { useAuth } from "../lib/auth"
import { useT } from "../lib/i18n"

type NagPayload = {
  available: boolean
  reason?: string
  installed?: string
  latest?: {
    tag: string | null
    name: string | null
    url: string
    body_preview?: string
  }
}

const ADMIN_ROLES = ["Hotel Admin", "System Manager", "Administrator"]
const SNOOZE_DAYS = 7

/** WordPress-style banner when this site is behind the latest GitHub release.
 * Admins only; guided upgrade via System Health - never auto-applies. */
export default function UpdateNag() {
  const { t } = useT()
  const { roles, status } = useAuth()
  const [nag, setNag] = useState<NagPayload | null>(null)
  const [busy, setBusy] = useState(false)

  const isAdmin = ADMIN_ROLES.some((r) => roles.includes(r))

  useEffect(() => {
    if (status !== "authed" || !isAdmin) {
      setNag(null)
      return
    }
    let cancelled = false
    call<NagPayload>("kamra.health.update_nag")
      .then((out) => {
        if (!cancelled) setNag(out?.available ? out : null)
      })
      .catch(() => {
        if (!cancelled) setNag(null)
      })
    return () => {
      cancelled = true
    }
  }, [status, isAdmin])

  if (!nag?.available || !nag.latest?.tag) return null

  const tag = nag.latest.tag
  const latestLabel = tag.replace(/^v/, "")

  async function dismiss(snoozeDays: number) {
    setBusy(true)
    try {
      await call("kamra.health.dismiss_update_nag", {
        tag,
        snooze_days: snoozeDays,
      })
      setNag(null)
    } catch {
      // Keep the banner if dismiss fails - better noisy than silent.
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-2 border-b border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-950"
    >
      <div className="flex min-w-0 items-center gap-2">
        <ArrowUpCircle className="size-4 shrink-0 text-sky-700" aria-hidden />
        <p className="min-w-0">
          {t("Kamra {latest} is available - you are on {installed}.", {
            latest: latestLabel,
            installed: nag.installed ?? "-",
          })}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to="/health"
          className="rounded-md bg-sky-700 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-800"
        >
          {t("View update")}
        </Link>
        <button
          type="button"
          disabled={busy}
          onClick={() => void dismiss(SNOOZE_DAYS)}
          className="rounded-md px-2 py-1 text-xs font-medium text-sky-800 hover:bg-sky-100 disabled:opacity-50"
        >
          {t("Remind me later")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void dismiss(0)}
          aria-label={t("Dismiss")}
          title={t("Dismiss")}
          className="rounded-md p-1 text-sky-700 hover:bg-sky-100 disabled:opacity-50"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}
