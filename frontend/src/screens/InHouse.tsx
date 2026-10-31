import { useCallback, useEffect, useState } from "react"
import { useNavigate, useOutletContext, useSearchParams } from "react-router-dom"
import { ChevronLeft, ChevronRight, LogIn, LogOut, Receipt, Users } from "lucide-react"

import { getSnapshot, reservationDetail, type ReservationRow, type Snapshot } from "../lib/api"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Avatar } from "../components/ui/avatar"
import CheckInDialog from "../components/CheckInDialog"
import CheckOutDialog from "../components/CheckOutDialog"
import type { ShellContext } from "../AppShell"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"
import { serverError } from "../lib/resource"
import { useT, t as translate, uiDateLocale } from "../lib/i18n"

/** Everyone at the property on a day, in one place: who is due in, who is
 *  in house and who is due out, each with the desk's actions. */

type Tab = "arrivals" | "in-house" | "departures"
const TABS: { id: Tab; label: string; icon: typeof LogIn }[] = [
  { id: "arrivals", label: "Arrivals", icon: LogIn },
  { id: "in-house", label: "In house", icon: Users },
  { id: "departures", label: "Departures", icon: LogOut },
]

const iso = (d: Date) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return z.toISOString().slice(0, 10)
}
const shift = (day: string, n: number) => {
  const d = new Date(day + "T00:00:00")
  d.setDate(d.getDate() + n)
  return iso(d)
}
const money = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })}`
const short = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString(uiDateLocale(undefined), {
    day: "numeric",
    month: "short",
  })

function Balance({ row }: { row: ReservationRow }) {
  const { t } = useT()
  const due = Number(row.balance_due ?? 0)
  const paid = Number(row.paid_total ?? 0)
  if (due <= 0 && paid > 0) return <Badge tone="green">{t("Paid")}</Badge>
  if (due > 0) return <span className="font-medium tabular-nums text-amber-700">{money(due)}</span>
  return <span className="text-zinc-400">-</span>
}

export default function InHouse() {
  const { t } = useT()
  const navigate = useNavigate()
  const { refreshKey } = useOutletContext<ShellContext>()
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some((x) => x.id === params.get("tab")) ? params.get("tab") : "arrivals") as Tab
  const today = iso(new Date())
  const date = params.get("date") || today
  // expected arrivals over a range: date..until (one day when not set)
  const until = tab === "arrivals" && (params.get("until") ?? "") > date ? params.get("until")! : ""
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [rangeArrivals, setRangeArrivals] = useState<ReservationRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)

  const load = useCallback(() => {
    getSnapshot(date === today ? undefined : date)
      .then((s) => {
        setSnap(s)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [date, today])
  useEffect(load, [load, refreshKey])

  // ponytail: one snapshot per day, capped at 14 days; add a range endpoint
  // if desks want longer lists
  useEffect(() => {
    if (!until) { setRangeArrivals(null); return }
    const days: string[] = []
    for (let d = shift(date, 1); d <= until && days.length < 13; d = shift(d, 1)) days.push(d)
    let live = true
    Promise.all(days.map((d) => getSnapshot(d)))
      .then((snaps) => { if (live) setRangeArrivals(snaps.flatMap((s) => s.arrivals ?? [])) })
      .catch((e) => setError(serverError(e)))
    return () => { live = false }
  }, [date, until, refreshKey])

  const setQuery = (next: { tab?: Tab; date?: string; until?: string }) => {
    const p = new URLSearchParams(params)
    if (next.tab) p.set("tab", next.tab)
    if (next.until !== undefined) {
      if (next.until) p.set("until", next.until)
      else p.delete("until")
    }
    if (next.date !== undefined) {
      if (next.date === today) p.delete("date")
      else p.set("date", next.date)
    }
    setParams(p, { replace: true })
  }

  const rows: Record<Tab, ReservationRow[]> = {
    arrivals: [...(snap?.arrivals ?? []), ...(rangeArrivals ?? [])],
    "in-house": snap?.in_house ?? [],
    departures: snap?.departures ?? [],
  }
  const shown = rows[tab]

  async function openFolio(name: string) {
    try {
      const d = await reservationDetail(name)
      if (d.folio_name) navigate(`/billing/${encodeURIComponent(d.folio_name)}`)
      else navigate(`/grc/${encodeURIComponent(name)}`)
    } catch (e) {
      setError(serverError(e))
    }
  }

  const prettyDate = new Date(date + "T00:00:00").toLocaleDateString(uiDateLocale(undefined), {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">{t("In House")}</h1>
          <p className="text-xs text-zinc-500">{t("Arrivals, guests in house and departures, in one list.")}</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-white p-0.5 text-sm">
          <button
            aria-label={t("Previous day")}
            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100"
            onClick={() => setQuery({ date: shift(date, -1) })}
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            className={cn("rounded-md px-2.5 py-1 font-medium", date === today ? "text-brand-700" : "text-zinc-700")}
            onClick={() => setQuery({ date: today })}
            title={t("Back to today")}
          >
            {prettyDate}
          </button>
          <button
            aria-label={t("Next day")}
            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100"
            onClick={() => setQuery({ date: shift(date, 1) })}
          >
            <ChevronRight className="size-4" />
          </button>
          {tab === "arrivals" && (
            <label className="flex items-center gap-1 border-s border-zinc-200 ps-2 text-xs text-zinc-500">
              {t("Until")}
              <input type="date" className="rounded-md px-1 py-1 text-sm text-zinc-700" value={until}
                min={shift(date, 1)} max={shift(date, 13)}
                onChange={(e) => setQuery({ until: e.target.value })} />
            </label>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:max-w-xl" role="tablist">
        {TABS.map((x) => (
          <button
            key={x.id}
            role="tab"
            aria-selected={tab === x.id}
            onClick={() => setQuery({ tab: x.id })}
            className={cn(
              "flex flex-col-reverse items-start gap-0.5 rounded-xl border px-3 py-2 text-start transition-colors sm:flex-row sm:items-center sm:justify-between sm:gap-2 sm:py-2.5",
              tab === x.id
                ? "border-brand-600 bg-brand-50 text-brand-800"
                : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300",
            )}
          >
            <span className="flex min-w-0 max-w-full items-center gap-1.5 text-xs font-medium sm:gap-2 sm:text-sm">
              <x.icon className="hidden size-4 shrink-0 sm:block" aria-hidden />
              <span className="truncate">{t(x.label)}</span>
            </span>
            <span className="text-lg font-semibold tabular-nums">{rows[x.id].length}</span>
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
        {shown.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-zinc-400">
            {tab === "arrivals"
              ? t("No arrivals on this day.")
              : tab === "departures"
                ? t("No departures on this day.")
                : t("Nobody is in house.")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 text-left text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  <th className="px-4 py-2.5">{t("Guest")}</th>
                  <th className="px-3 py-2.5">{t("Room")}</th>
                  <th className="hidden px-3 py-2.5 sm:table-cell">{t("Stay")}</th>
                  <th className="hidden px-3 py-2.5 md:table-cell">{t("Source")}</th>
                  <th className="px-3 py-2.5 text-right">{t("Due")}</th>
                  <th className="px-4 py-2.5 text-right">{t("Actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {shown.map((row) => (
                  <tr
                    key={row.name}
                    className="cursor-pointer hover:bg-zinc-50"
                    onClick={() => navigate(`/grc/${encodeURIComponent(row.name)}`)}
                  >
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={row.guest_name} />
                        <div className="min-w-0">
                          <div className="truncate font-medium text-zinc-900">{row.guest_name}</div>
                          <div className="text-xs text-zinc-500">
                            {t("{n} ad", { n: row.adults })}
                            {row.children ? translate(" + {v0} ch", { v0: String(row.children) }) : ""}
                            {row.eta && translate(" · ETA {v0}", { v0: String(row.eta) })}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 tabular-nums">
                      {row.room ? row.room.split("-").pop() : <span className="text-zinc-400">{t("Unassigned")}</span>}
                    </td>
                    <td className="hidden px-3 py-2.5 text-zinc-600 sm:table-cell">
                      {short(row.check_in_date)} - {short(row.check_out_date)}
                      <span className="text-zinc-400"> · {t("{n} night{s}", { n: row.nights, s: row.nights === 1 ? "" : "s" })}</span>
                    </td>
                    <td className="hidden px-3 py-2.5 md:table-cell">
                      <Badge tone={row.source === "OTA" ? "indigo" : row.source === "AI Agent" ? "brand" : "zinc"}>
                        {row.source === "OTA" ? row.channel || t("OTA") : t(row.source)}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Balance row={row} />
                    </td>
                    <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-1.5">
                        {tab === "arrivals" && date === today && (
                          <Button className="px-2.5 py-1 text-xs" onClick={() => setCheckingIn(row.name)}>
                            {t("Check in")}
                          </Button>
                        )}
                        {tab !== "arrivals" && (
                          <Button
                            variant={tab === "departures" ? "primary" : "outline"}
                            className="px-2.5 py-1 text-xs"
                            onClick={() => setCheckingOut(row.name)}
                          >
                            {t("Check out")}
                          </Button>
                        )}
                        {tab !== "arrivals" && (
                          <Button
                            variant="ghost"
                            className="px-2 py-1 text-xs"
                            title={t("Open folio")}
                            aria-label={t("Open folio")}
                            onClick={() => void openFolio(row.name)}
                          >
                            <Receipt className="size-3.5" aria-hidden />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            load()
          }}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            load()
          }}
          onOpenReservation={(name) => setCheckingOut(name)}
        />
      )}
    </div>
  )
}
