import { useCallback, useEffect, useState } from "react"
import { Inbox } from "lucide-react"
import {
  acceptBookingRequest,
  call,
  declineBookingRequest,
  getCurrentProperty,
} from "../lib/api"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import { serverError } from "../lib/resource"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { useAuth } from "../lib/auth"

// kamra.booking_requests.booking_requests: Front Desk, plus the admins
const INBOX_ROLES = ["Front Desk", "Hotel Admin", "System Manager", "Administrator", "Kamra Agent"]

type BookingRequest = {
  name: string
  guest_name: string
  room_type: string
  room_type_name: string
  check_in_date: string
  check_out_date: string
  nights: number
  adults: number
  children: number
  source: string
  channel?: string | null
  amount_after_tax?: number | null
  special_requests?: string | null
  rooms_free: number
  can_accept: boolean
  blocker?: string | null
}

type InboxData = { holds_inventory: boolean; count: number; requests: BookingRequest[] }

const money0 = (n: number) =>
  Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

/** Request-to-Book inbox on Today: stays waiting for the host's yes / no.
 * A request holds no room until it is accepted, so "rooms free" is live
 * availability - accept re-checks it and refuses if the dates sold. */
export default function BookingRequests({
  refreshKey,
  onChanged,
}: {
  refreshKey?: unknown
  onChanged?: () => void
}) {
  const { t } = useT()
  const { roles } = useAuth()
  // a role without the inbox does not ask for it (the server says 403)
  const canSee = roles.some((r) => INBOX_ROLES.includes(r))
  const [data, setData] = useState<InboxData | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [declining, setDeclining] = useState<string | null>(null)
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(
        await call<InboxData>("kamra.booking_requests.booking_requests", {
          property: getCurrentProperty(),
        }),
      )
    } catch {
      setData(null) // a role without the inbox just doesn't see the card
    }
  }, [])

  useEffect(() => {
    if (!canSee) return
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [load, refreshKey, canSee])

  async function run(key: string, fn: () => Promise<{ notified?: string[] }>, done: string) {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      const out = await fn()
      const told = out?.notified?.length
        ? t("Guest told by {via}.", { via: out.notified.join(", ") })
        : ""
      setNotice(`${done} ${told}`.trim())
      setDeclining(null)
      setReason("")
      await load()
      onChanged?.()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  if (!data || data.count === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {t("Booking requests")}
          <Badge tone="amber">{data.count}</Badge>
        </CardTitle>
        <Inbox className="size-4 text-zinc-400" aria-hidden />
      </CardHeader>
      <CardContent className="pt-1">
        <p className="mb-2 text-xs text-zinc-500">
          {t("Requests don't hold a room. Accepting checks availability again.")}
        </p>
        {error && (
          <p className="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs text-rose-700">
            {error}
          </p>
        )}
        {notice && (
          <p className="mb-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-800">
            {notice}
          </p>
        )}
        <ul className="divide-y divide-zinc-100">
          {data.requests.map((r) => (
            <li key={r.name} className="py-2.5">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium">{r.guest_name}</span>
                    <Badge tone={r.source === "OTA" ? "indigo" : "zinc"}>
                      {r.source === "OTA" ? r.channel || t("OTA") : t(r.source)}
                    </Badge>
                    {r.can_accept ? (
                      <Badge tone="green">
                        {t("{n} free now", { n: r.rooms_free })}
                      </Badge>
                    ) : (
                      <Badge tone="rose" title={r.blocker ?? undefined}>
                        {t("Sold out")}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-zinc-500">
                    {r.room_type_name} · {r.check_in_date} → {r.check_out_date} ·{" "}
                    {t("{n} night{s}", { n: r.nights, s: r.nights === 1 ? "" : "s" })} ·{" "}
                    {t("{n} ad", { n: r.adults })}
                    {r.children ? ` + ${r.children} ch` : ""}
                    {Number(r.amount_after_tax) > 0 &&
                      ` · ${cur()}${money0(Number(r.amount_after_tax))}`}
                  </div>
                  {!r.can_accept && r.blocker && (
                    <div className="mt-0.5 text-xs text-rose-600">{r.blocker}</div>
                  )}
                  {r.special_requests && (
                    <div className="mt-0.5 line-clamp-2 text-xs text-zinc-400">
                      {r.special_requests}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    disabled={busy === r.name || !r.can_accept}
                    title={r.can_accept ? undefined : r.blocker ?? undefined}
                    onClick={() =>
                      run(
                        r.name,
                        () =>
                          acceptBookingRequest(r.name),
                        t("Accepted {name}.", { name: r.name }),
                      )
                    }
                  >
                    {t("Accept")}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busy === r.name}
                    onClick={() => {
                      setDeclining(declining === r.name ? null : r.name)
                      setReason("")
                    }}
                  >
                    {t("Decline")}
                  </Button>
                </div>
              </div>
              {declining === r.name && (
                <form
                  className="mt-2 flex items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault()
                    if (!reason.trim()) return
                    run(
                      r.name,
                      () =>
                        declineBookingRequest(r.name, reason.trim()),
                      t("Declined {name}.", { name: r.name }),
                    )
                  }}
                >
                  <input
                    autoFocus
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={t("Reason (sent to the guest)")}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                  />
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={!reason.trim() || busy === r.name}
                  >
                    {t("Decline request")}
                  </Button>
                </form>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
