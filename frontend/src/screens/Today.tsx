import { useCallback, useEffect, useState } from "react"
import {
  BedDouble,
  LogIn,
  LogOut,
  Users,
  Wallet,
  ListChecks,
  PieChart,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { useOutletContext } from "react-router-dom"
import {
  call,
  checkOut,
  getCurrentProperty,
  getSnapshot,
  setHousekeepingStatus,
  type ReservationRow,
  type RoomRow,
  type Snapshot,
} from "../lib/api"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { StatCard } from "../components/ui/stat-card"
import { cn } from "../lib/utils"
import type { ShellContext } from "../AppShell"
import CheckInDialog from "../components/CheckInDialog"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { cur, moneyLocale } from "../lib/money"

const HK_CYCLE: RoomRow["housekeeping_status"][] = [
  "Dirty",
  "Clean",
  "Inspected",
  "Out of Order",
]

const hkTone: Record<RoomRow["housekeeping_status"], string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}

const inr0 = (n: number) =>
  Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

/** Paid / due / unpaid at a glance - the folio is the source of truth,
 * this chip just saves the trip to Billing. */
function paymentChip(row: ReservationRow) {
  const paid = Number(row.paid_total ?? 0)
  const due = Number(row.balance_due ?? 0)
  if (due <= 0 && paid > 0) return <Badge tone="green">Paid</Badge>
  if (paid > 0)
    return <Badge tone="amber">{cur()}{inr0(due)} due</Badge>
  if (due > 0) return <Badge tone="zinc">Unpaid</Badge>
  return null
}

function sourceBadge(row: ReservationRow) {
  if (row.source === "AI Agent") return <Badge tone="brand">AI Agent</Badge>
  if (row.source === "OTA")
    return <Badge tone="indigo">{row.channel || "OTA"}</Badge>
  return <Badge tone="zinc">{row.source}</Badge>
}

// Illustrative micro-trend for the KPI sparklines until a history endpoint
// lands; the headline value itself is always real.
const mkTrend = (n: number, up = true) =>
  Array.from({ length: 8 }, (_, i) => {
    const b = Math.max(1, Math.abs(n))
    const t = i / 7
    return b * (0.78 + (up ? t : 1 - t) * 0.3 + Math.sin(i * 1.6) * 0.05)
  })

function ReservationList(props: {
  rows: ReservationRow[]
  empty: string
  action: (row: ReservationRow) => React.ReactNode
}) {
  if (props.rows.length === 0) {
    return <p className="px-1 py-3 text-sm text-zinc-400">{props.empty}</p>
  }
  return (
    <ul className="divide-y divide-zinc-100">
      {props.rows.map((row) => (
        <li key={row.name} className="flex items-center gap-3 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {row.guest_name}
              </span>
              {sourceBadge(row)}
              {paymentChip(row)}
              {row.precheckin_status === "Submitted" && (
                <Badge tone="green">Pre-checked-in</Badge>
              )}
            </div>
            <div className="mt-0.5 text-xs text-zinc-500">
              {row.room ? `Room ${row.room.split("-").pop()}` : "Unassigned"} ·{" "}
              {row.nights} night{row.nights === 1 ? "" : "s"} · {row.adults} ad
              {row.children ? ` + ${row.children} ch` : ""}
              {row.eta && ` · ETA ${row.eta}`}
              {row.booked_by_name && (
                <span
                  title={
                    (row.booked_by_phone
                      ? `${row.booked_by_phone} · `
                      : "") +
                    `send links & updates to: ${row.contact_preference ?? "Booker"}`
                  }
                >
                  {" "}
                  · via {row.booked_by_name}
                  {row.booker_relation ? ` (${row.booker_relation})` : ""}
                </span>
              )}
              {row.status === "Confirmed" && (
                <a
                  href={toFullPath(`/grc/${encodeURIComponent(row.name)}`)}
                  className="ml-2 font-medium text-brand-700 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  GRC
                </a>
              )}
              {row.status === "Confirmed" &&
                row.precheckin_status !== "Submitted" &&
                row.precheckin_token && (
                  <button
                    className="ml-2 font-medium text-brand-700 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigator.clipboard.writeText(
                        `${window.location.origin}/checkin/${row.precheckin_token}`,
                      )
                    }}
                    title={`Copy the self check-in link - send to the ${
                      row.contact_preference === "Booker" && row.booked_by_name
                        ? `booker, ${row.booked_by_name}${row.booked_by_phone ? ` (${row.booked_by_phone})` : ""}`
                        : row.contact_preference === "Both" && row.booked_by_name
                          ? `guest and the booker (${row.booked_by_name})`
                          : "guest"
                    }`}
                  >
                    copy check-in link
                  </button>
                )}
            </div>
          </div>
          {props.action(row)}
        </li>
      ))}
    </ul>
  )
}

export default function Today() {
  const { refreshKey } = useOutletContext<ShellContext>()
  const [snap, setSnap] = useState<Snapshot | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [kpi, setKpi] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([
        getSnapshot(),
        call("kamra.dashboards.property_dashboard", {
          property: getCurrentProperty(),
        }).catch(() => null),
      ])
      setSnap(s)
      setKpi(k)
      setError(null)
    } catch (e) {
      setError(serverError(e))
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 30_000)
    return () => clearInterval(t)
  }, [refresh, refreshKey])

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key)
    try {
      await fn()
      await refresh()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  const occupied = snap?.rooms.filter(
    (r) => r.occupancy_status === "Occupied",
  ).length
  const occupancyPct = snap?.rooms.length
    ? Math.round(((occupied ?? 0) / snap.rooms.length) * 100)
    : 0
  const arrivalsN = snap?.arrivals.length ?? 0
  const departuresN = snap?.departures.length ?? 0
  const inhouseN = snap?.in_house.length ?? 0
  const roomsN = snap?.rooms.length ?? 0
  const revenue = Number(kpi?.revenue_today ?? 0)
  const revpar = Number(kpi?.statistics?.revpar ?? 0)
  const tasksN = Number(kpi?.housekeeping?.open_tasks ?? 0)
  const overdueN = Number(kpi?.housekeeping?.overdue_tasks ?? 0)
  const hh = new Date().getHours()
  const greeting =
    hh < 12 ? "Good morning" : hh < 17 ? "Good afternoon" : "Good evening"
  const prettyDate = snap?.date
    ? new Date(snap.date + "T00:00:00").toLocaleDateString(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : ""

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">
            Front Desk Overview
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            {greeting}. Here's what's happening today.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-white p-1 text-sm">
          <button
            className="grid size-7 place-items-center rounded-md text-zinc-400 hover:bg-zinc-50"
            aria-label="Previous day"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="px-2 font-medium tabular-nums text-zinc-700">
            {prettyDate}
          </span>
          <button
            className="grid size-7 place-items-center rounded-md text-zinc-400 hover:bg-zinc-50"
            aria-label="Next day"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<LogIn className="size-4" />}
          label="Arrivals Today"
          value={arrivalsN}
          spark={mkTrend(arrivalsN)}
        />
        <StatCard
          icon={<LogOut className="size-4" />}
          label="Departures Today"
          value={departuresN}
          spark={mkTrend(departuresN, false)}
          sparkColor="var(--color-amber-600)"
        />
        <StatCard
          icon={<Users className="size-4" />}
          label="In-house Guests"
          value={inhouseN}
          spark={mkTrend(inhouseN)}
        />
        <StatCard
          icon={<PieChart className="size-4" />}
          label="Occupancy"
          value={`${occupancyPct}%`}
          progress={occupancyPct}
          progressLabel={`${occupied ?? 0} of ${roomsN} rooms`}
        />
        <StatCard
          icon={<Wallet className="size-4" />}
          label="Revenue / RevPAR"
          value={`${cur()}${inr0(revenue)}`}
          sub={`RevPAR ${cur()}${inr0(revpar)}`}
          spark={mkTrend(revenue)}
        />
        <StatCard
          icon={<ListChecks className="size-4" />}
          label="Tasks Pending"
          value={tasksN}
          sub={overdueN ? `${overdueN} overdue` : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Arrivals</CardTitle>
              <LogIn className="size-4 text-zinc-400" aria-hidden />
            </CardHeader>
            <CardContent className="pt-1">
              <ReservationList
                rows={snap?.arrivals ?? []}
                empty="No arrivals expected today."
                action={(row) => (
                  <Button
                    disabled={busy === row.name}
                    onClick={() => setCheckingIn(row.name)}
                  >
                    Check in
                  </Button>
                )}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Departures</CardTitle>
              <LogOut className="size-4 text-zinc-400" aria-hidden />
            </CardHeader>
            <CardContent className="pt-1">
              <ReservationList
                rows={snap?.departures ?? []}
                empty="No departures due today."
                action={(row) => (
                  <Button
                    variant="outline"
                    disabled={busy === row.name}
                    onClick={() => act(row.name, () => checkOut(row.name))}
                  >
                    Check out
                  </Button>
                )}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4 lg:col-span-3">
          <Card>
            <CardHeader>
              <CardTitle>Room board</CardTitle>
              <span className="text-xs text-zinc-400">
                Click a room to advance its housekeeping status
              </span>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 md:grid-cols-7">
                {(snap?.rooms ?? []).map((room) => {
                  const next =
                    HK_CYCLE[
                      (HK_CYCLE.indexOf(room.housekeeping_status) + 1) %
                        HK_CYCLE.length
                    ]
                  return (
                    <button
                      key={room.name}
                      title={`${room.housekeeping_status} → ${next}`}
                      disabled={busy === room.name}
                      onClick={() =>
                        act(room.name, () =>
                          setHousekeepingStatus(room.name, next),
                        )
                      }
                      className={cn(
                        "rounded-lg border px-2 pb-1.5 pt-2 text-left transition-transform",
                        "hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
                        hkTone[room.housekeeping_status],
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold">
                          {room.room_number}
                        </span>
                        {room.occupancy_status === "Occupied" && (
                          <BedDouble className="size-3.5" aria-hidden />
                        )}
                      </div>
                      <div className="mt-0.5 truncate text-[10px] font-medium uppercase tracking-wide opacity-70">
                        {room.housekeeping_status}
                      </div>
                    </button>
                  )
                })}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
                <Badge tone="green">Clean</Badge>
                <Badge tone="sky">Inspected</Badge>
                <Badge tone="amber">Dirty</Badge>
                <Badge tone="rose">Out of Order</Badge>
                <span className="inline-flex items-center gap-1">
                  <BedDouble className="size-3.5" aria-hidden /> occupied
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>In-house guests</CardTitle>
            </CardHeader>
            <CardContent className="pt-1">
              <ReservationList
                rows={snap?.in_house ?? []}
                empty="Nobody is checked in right now."
                action={(row) => (
                  <span className="text-xs text-zinc-400">
                    until {row.check_out_date}
                  </span>
                )}
              />
            </CardContent>
          </Card>
        </div>
      </div>
      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            refresh()
          }}
        />
      )}
    </div>
  )
}
