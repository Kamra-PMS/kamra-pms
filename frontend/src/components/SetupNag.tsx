import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ListChecks, X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { useT } from "../lib/i18n"
import type { Checklist } from "../screens/FinishSetup"

const ADMIN_ROLES = ["Hotel Admin", "System Manager", "Administrator"]

const key = (p: string) => `kamra.setupnag.${p}`

/** A slim bar until the property's setup list is done. Admins only; the
 *  X hides it for a week on this browser. */
export default function SetupNag() {
  const { t } = useT()
  const { roles, status } = useAuth()
  const [list, setList] = useState<Checklist | null>(null)
  const property = getCurrentProperty()
  const isAdmin = ADMIN_ROLES.some((r) => roles.includes(r))

  useEffect(() => {
    if (status !== "authed" || !isAdmin || !property) return
    try {
      const until = Number(localStorage.getItem(key(property)) || 0)
      if (until > Date.now()) return
    } catch {
      /* private window: just show it */
    }
    call<Checklist>("kamra.onboarding.setup_checklist", { property })
      .then((c) => setList(c.percent < 100 ? c : null))
      .catch(() => setList(null))
  }, [status, isAdmin, property])

  if (!list) return null
  return (
    <div className="flex items-center gap-3 border-b border-brand-200 bg-brand-50 px-4 py-2 text-sm text-brand-800">
      <ListChecks className="size-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">
        {t("Finish setting up: {done} of {total} done.", { done: list.done, total: list.total })}{" "}
        <Link to="/finish-setup" className="font-medium underline">{t("See what is left")}</Link>
      </span>
      <button
        type="button"
        aria-label={t("Hide for a week")}
        onClick={() => {
          try {
            localStorage.setItem(key(property), String(Date.now() + 7 * 86400000))
          } catch {
            /* ignore */
          }
          setList(null)
        }}
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  )
}
