/*  Sounds and shows an alert when something new lands that someone else
    made: a booking, a service ticket, a laundry order. Mounted once in the
    app shell. It listens to the same live-update event every screen uses
    (the server says whether the document is new and who made the change as
    a hash, so your own actions stay quiet), ignores other properties, and
    honours the switches in lib/notifications.ts. The POS and kitchen sounds
    are not here: the kitchen screen sounds its own tickets on its own switch. */

import { useEffect } from "react"
import { X } from "lucide-react"
import { getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { subscribeRealtime, type ChangeEvent } from "../lib/realtime"
import { dismissAlert, getPref, pushAlert, useAlerts, who } from "../lib/notifications"
import { playAlert, unlockSound } from "../lib/sound"
import { useT } from "../lib/i18n"

export default function NotificationHost() {
  const { user } = useAuth()
  const { t } = useT()
  const alerts = useAlerts()

  useEffect(() => {
    unlockSound()
    const me = who(user)
    const say = (e: ChangeEvent) => {
      if (!e.is_new || !e.name) return
      if (e.by && e.by === me) return // your own action
      const prop = getCurrentProperty()
      if (e.property && prop && e.property !== prop) return
      if (!getPref("notify")) return
      const name = e.name
      const text =
        e.doctype === "Reservation" ? t("New booking {name}", { name })
        : e.doctype === "Service Ticket" ? t("New service ticket {name}", { name })
        : e.doctype === "Laundry Order" ? t("New laundry order {name}", { name })
        : null
      if (!text) return
      pushAlert(text)
      playAlert("general")
    }
    // the filter sees every event; nothing here needs a re-fetch, so it
    // always answers "skip" and the long fallback keeps polling idle
    return subscribeRealtime(() => {}, { filter: (e) => { say(e); return false }, fallbackMs: 3_600_000 })
  }, [user, t])

  if (alerts.length === 0) return null
  return (
    <div className="pointer-events-none fixed bottom-4 end-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
      {alerts.map((a) => (
        <div key={a.id} role="status"
          className="pointer-events-auto flex items-start gap-2 rounded-xl border border-brand-200 bg-white px-3 py-2.5 text-sm text-zinc-800 shadow-lg">
          <span className="mt-1 size-2 shrink-0 rounded-full bg-brand-600" aria-hidden />
          <span className="min-w-0 flex-1">{a.text}</span>
          <button onClick={() => dismissAlert(a.id)} aria-label={t("Dismiss")}
            className="rounded p-0.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
