/** The bell in the top bar: what each department should know, kept for 30
 *  days. A person sees only the modules they work in (kamra.notifications
 *  decides), and the count is what arrived since they last opened it. */
import { useCallback, useEffect, useRef, useState } from "react"
import { Bell } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { call } from "../lib/api"
import { getLang } from "../lib/dir"
import { useT } from "../lib/i18n"
import { subscribeRealtime } from "../lib/realtime"
import { playAlert } from "../lib/sound"
import { cn } from "../lib/utils"

interface Item {
  name: string
  module: string
  subject: string
  route: string | null
  age: number
}
interface BellData {
  modules: string[]
  unread: number
  items: Item[]
}

const MODULE_NAMES: Record<string, string> = {
  "front-desk": "Front Desk",
  housekeeping: "Housekeeping",
  operations: "Operations",
  fnb: "F&B",
  events: "Events",
  finance: "Finance",
  revenue: "Revenue",
}

function ago(age: number): string {
  const secs = -age
  const rtf = new Intl.RelativeTimeFormat(getLang(), { numeric: "auto", style: "short" })
  const abs = Math.abs(secs)
  if (abs < 60) return rtf.format(0, "second")
  if (abs < 3600) return rtf.format(Math.round(secs / 60), "minute")
  if (abs < 86400) return rtf.format(Math.round(secs / 3600), "hour")
  return rtf.format(Math.round(secs / 86400), "day")
}

export default function NotificationBell({ property }: { property: string }) {
  const { t } = useT()
  const navigate = useNavigate()
  const [data, setData] = useState<BellData | null>(null)
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState("all")
  const ref = useRef<HTMLDivElement>(null)

  // every line already heard; null until the first load, so opening the
  // app doesn't ring for what was waiting, and a line leaving the list
  // (opened) never rings either
  const heard = useRef<Set<string> | null>(null)

  const load = useCallback(() => {
    if (!property) return
    call<BellData>("kamra.notifications.bell", { property })
      .then((d) => {
        const known = heard.current
        if (known && d.items.some((i) => !known.has(i.name))) {
          playAlert("general") // follows the sound switch in Alerts and sound
        }
        heard.current = new Set([...(known ?? []), ...d.items.map((i) => i.name)])
        setData(d)
      })
      .catch(() => {}) // the bell is a convenience; never break the shell
  }, [property])

  // a new property starts quiet again
  useEffect(() => {
    heard.current = null
  }, [property])

  useEffect(() => {
    load()
    return subscribeRealtime(load, {
      filter: (e) => e.doctype === "Kamra Notification" && (!e.property || e.property === property),
      fallbackMs: 60_000,
    })
  }, [load, property])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener("mousedown", onDown)
    return () => window.removeEventListener("mousedown", onDown)
  }, [open])

  if (!data || data.modules.length === 0) return null

  const markRead = () => {
    setData((d) => d && { ...d, unread: 0, items: [] })
    call("kamra.notifications.mark_read", { property }).catch(() => {})
  }

  // opening one takes it off this person's list
  const openOne = (i: Item) => {
    setOpen(false)
    setData((d) => d && {
      ...d,
      unread: Math.max(d.unread - 1, 0),
      items: d.items.filter((x) => x.name !== i.name),
    })
    call("kamra.notifications.open_one", { property, notification: i.name }).catch(() => {})
    if (i.route) navigate(i.route)
  }

  const items = tab === "all" ? data.items : data.items.filter((i) => i.module === tab)
  const tabs = data.modules.length > 1 ? ["all", ...data.modules] : []

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={t("Notifications")}
        title={t("Notifications")}
        className="relative rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
      >
        <Bell className="size-4" aria-hidden />
        {data.unread > 0 && (
          <span className="absolute -end-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold leading-none text-white">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute end-0 top-10 z-50 flex max-h-[70vh] w-[22rem] max-w-[calc(100vw-2rem)] flex-col rounded-lg border border-zinc-200 bg-white shadow-lg ring-1 ring-black/5 dark:border-zinc-700 dark:bg-zinc-900">
          <div className="flex items-center justify-between border-b border-zinc-100 px-3 py-2 dark:border-zinc-800">
            <span className="text-sm font-semibold">{t("Notifications")}</span>
            {data.unread > 0 && (
              <button
                onClick={markRead}
                className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-400"
              >
                {t("Mark all read")}
              </button>
            )}
          </div>
          {tabs.length > 0 && (
            <div className="flex flex-wrap gap-1 border-b border-zinc-100 px-3 py-2 dark:border-zinc-800">
              {tabs.map((m) => (
                <button
                  key={m}
                  onClick={() => setTab(m)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 text-xs",
                    tab === m
                      ? "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
                      : "border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800",
                  )}
                >
                  {m === "all" ? t("All") : t(MODULE_NAMES[m] ?? m)}
                </button>
              ))}
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-zinc-400">{t("Nothing new.")}</p>
            ) : (
              items.map((i) => (
                <button
                  key={i.name}
                  onClick={() => openOne(i)}
                  className="flex w-full items-start gap-2 border-b border-zinc-50 px-3 py-2.5 text-start last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800"
                >
                  <span className="mt-1.5 size-2 shrink-0 rounded-full bg-brand-600" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {i.subject}
                    </span>
                    <span className="mt-0.5 block text-xs text-zinc-400">
                      {t(MODULE_NAMES[i.module] ?? i.module)} · {ago(i.age)}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
