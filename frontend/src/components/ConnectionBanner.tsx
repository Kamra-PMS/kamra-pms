import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"
import { whoami } from "../lib/api"

/** A single, calm strip when the server can't be reached — instead of raw
 * fetch errors scattered across screens. The api layer emits kamra:offline
 * on network failure and kamra:online on any success; while offline we ping
 * quietly until the server answers, then the strip disappears and the
 * screens' own polling/realtime refetch recovers the data. */
export default function ConnectionBanner() {
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    const off = () => setOffline(true)
    const on = () => setOffline(false)
    window.addEventListener("kamra:offline", off)
    window.addEventListener("kamra:online", on)
    window.addEventListener("online", off) // browser back online → verify
    return () => {
      window.removeEventListener("kamra:offline", off)
      window.removeEventListener("kamra:online", on)
      window.removeEventListener("online", off)
    }
  }, [])

  // while offline, probe every 5s; the first success emits kamra:online
  useEffect(() => {
    if (!offline) return
    const t = setInterval(() => {
      whoami().catch(() => undefined)
    }, 5000)
    return () => clearInterval(t)
  }, [offline])

  if (!offline) return null
  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-[100] flex items-center justify-center gap-2 bg-amber-500 px-4 py-1.5 text-sm font-medium text-white shadow"
    >
      <WifiOff className="size-4" aria-hidden />
      Connection lost — reconnecting…
    </div>
  )
}
