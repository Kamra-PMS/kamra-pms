/*  The alert switches, one tap from the sidebar: notifications on or off,
    the notification sound on or off, and the POS and kitchen sound on its
    own. Kept on this device. "Test sound" plays the file whatever the
    switches say, which also unlocks audio in the browser. */

import { useState } from "react"
import { Bell, BellOff } from "lucide-react"
import { usePref, type Pref } from "../lib/notifications"
import { previewSound } from "../lib/sound"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"

function Switch({ pref, title, hint, disabled }: {
  pref: Pref; title: string; hint: string; disabled?: boolean
}) {
  const [on, set] = usePref(pref)
  return (
    <label className={cn("flex items-start gap-2.5 py-1.5", disabled && "opacity-50")}>
      <input type="checkbox" role="switch" className="mt-0.5 size-4 accent-brand-600"
        checked={on} disabled={disabled} onChange={(e) => set(e.target.checked)} />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-zinc-800">{title}</span>
        <span className="block text-xs text-zinc-500">{hint}</span>
      </span>
    </label>
  )
}

export default function AlertSettings() {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [notify] = usePref("notify")
  return (
    <div className="px-1">
      {open && (
        <div className="mb-2 rounded-xl border border-zinc-200 bg-white p-3 shadow-sm">
          <Switch pref="notify" title={t("Notifications")}
            hint={t("An alert on screen when a booking, ticket or laundry order comes in.")} />
          <Switch pref="sound" disabled={!notify} title={t("Notification sound")}
            hint={t("Play a sound with those alerts.")} />
          <Switch pref="pos" title={t("POS and kitchen sound")}
            hint={t("A sound for new orders at the kitchen. Separate from the rest.")} />
          <button onClick={previewSound}
            className="mt-1 text-xs font-medium text-brand-700 hover:underline">
            {t("Test sound")}
          </button>
          <p className="mt-2 text-[11px] text-zinc-400">{t("These apply to this device only.")}</p>
        </div>
      )}
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800">
        {notify ? <Bell className="size-4" aria-hidden /> : <BellOff className="size-4" aria-hidden />}
        {t("Alerts and sound")}
      </button>
    </div>
  )
}
