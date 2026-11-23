import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"
import { replayOffline, whoami } from "../lib/api"
import * as offline from "../lib/offline"
import { useT } from "../lib/i18n"

const store = (): offline.Store | null => {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** A single, calm strip when the server can't be reached - instead of raw
 * fetch errors scattered across screens. The api layer emits kamra:offline
 * on network failure and kamra:online on any success; while offline we ping
 * quietly until the server answers, then the strip disappears and the
 * screens' own polling/realtime refetch recovers the data.
 *
 * During an outage (#228) Today, arrivals and the room board show their
 * last copy (kamra:stale carries when it was synced) and room / task status
 * changes are queued (kamra:queue). Back online, the queue is sent; what the
 * server refused (someone changed it meanwhile) is listed here. */
export default function ConnectionBanner() {
  const { t } = useT()
  const [offlineNow, setOffline] = useState(() => !navigator.onLine)
  const [syncedAt, setSyncedAt] = useState<number | null>(null)
  const [pending, setPending] = useState(() => offline.queued(store() ?? localStorageStub).length)
  const [refused, setRefused] = useState(() => offline.failed(store() ?? localStorageStub))

  useEffect(() => {
    const off = () => setOffline(true)
    const on = () => {
      setOffline(false)
      setSyncedAt(null)
      void replayOffline()
    }
    const stale = (e: Event) => setSyncedAt((e as CustomEvent<number>).detail)
    const queue = () => {
      const s = store()
      setPending(s ? offline.queued(s).length : 0)
      setRefused(s ? offline.failed(s) : [])
    }
    window.addEventListener("kamra:offline", off)
    window.addEventListener("kamra:online", on)
    window.addEventListener("kamra:stale", stale)
    window.addEventListener("kamra:queue", queue)
    window.addEventListener("offline", off) // the device lost its network
    window.addEventListener("online", off) // browser back online → verify
    void replayOffline() // anything left from a session that closed offline
    return () => {
      window.removeEventListener("kamra:offline", off)
      window.removeEventListener("kamra:online", on)
      window.removeEventListener("kamra:stale", stale)
      window.removeEventListener("kamra:queue", queue)
      window.removeEventListener("offline", off)
      window.removeEventListener("online", off)
    }
  }, [])

  // while offline, probe every 5s; the first success emits kamra:online
  useEffect(() => {
    if (!offlineNow) return
    const id = setInterval(() => {
      whoami().catch(() => undefined)
    }, 5000)
    return () => clearInterval(id)
  }, [offlineNow])

  const time = (at: number) => new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  if (!offlineNow && !refused.length) return null
  return (
    <div role="status" className="fixed inset-x-0 top-0 z-[100] text-sm font-medium text-white shadow">
      {offlineNow && (
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-0.5 bg-amber-500 px-4 py-1.5">
          <span className="flex items-center gap-2">
            <WifiOff className="size-4" aria-hidden />
            {t("Connection lost - reconnecting…")}
          </span>
          {syncedAt && <span>{t("Showing data from {time}. View only.", { time: time(syncedAt) })}</span>}
          {pending > 0 && <span>{t("{n} room status change(s) will be sent when you're back online.", { n: pending })}</span>}
        </div>
      )}
      {refused.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-x-3 bg-rose-600 px-4 py-1.5">
          <span>{t("Not applied after the outage:")}</span>
          {refused.map((f) => <span key={f.id}>{f.label}: {f.error}</span>)}
          <button type="button" className="underline"
            onClick={() => { const s = store(); if (s) offline.clearFailed(s); setRefused([]) }}>
            {t("Dismiss")}
          </button>
        </div>
      )}
    </div>
  )
}

// storage blocked (private mode): nothing queued, nothing refused
const localStorageStub: offline.Store = {
  getItem: () => null, setItem: () => undefined, removeItem: () => undefined,
  key: () => null, length: 0,
}
