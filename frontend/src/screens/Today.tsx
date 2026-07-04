import { useCallback, useEffect, useState } from "react"
import { BedDouble, LogIn, LogOut, Sparkles } from "lucide-react"
import { useOutletContext } from "react-router-dom"
import {
  checkIn,
  checkOut,
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
import { cn } from "../lib/utils"
import type { ShellContext } from "../AppShell"

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

function sourceBadge(row: ReservationRow) {
  if (row.source === "AI Agent") return <Badge tone="brand">AI Agent</Badge>
  if (row.source === "OTA")
    return <Badge tone="indigo">{row.channel || "OTA"}</Badge>
  return <Badge tone="zinc">{row.source}</Badge>
}

function StatTile(props: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold">{props.value}</div>
        <div className="mt-0.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
          {props.label}
        </div>
        {props.hint && (
          <div className="mt-1 text-xs text-zinc-400">{props.hint}</div>
        )}
      </CardContent>
    </Card>
  )
}

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
            </div>
            <div className="mt-0.5 text-xs text-zinc-500">
              {row.room ? `Room ${row.room.split("-").pop()}` : "Unassigned"} ·{" "}
              {row.nights} night{row.nights === 1 ? "" : "s"} · {row.adults} ad
              {row.children ? ` + ${row.children} ch` : ""}
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
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setSnap(await getSnapshot())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
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
      setError((e as Error).message)
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
  const hoursSaved = ((snap?.minutes_saved_30d ?? 0) / 60).toFixed(1)

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">
          Today
          <span className="ml-2 text-sm font-normal text-zinc-400">
            {snap?.date}
          </span>
        </h1>
        <Badge tone="brand" className="gap-1 px-2.5 py-1 text-sm">
          <Sparkles className="size-3.5" aria-hidden />
          {hoursSaved} hrs saved · 30 days
        </Badge>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error} — is the bench running on :8000?
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile
          label="Arrivals today"
          value={String(snap?.arrivals.length ?? "–")}
        />
        <StatTile
          label="Departures today"
          value={String(snap?.departures.length ?? "–")}
        />
        <StatTile
          label="In-house"
          value={String(snap?.in_house.length ?? "–")}
        />
        <StatTile
          label="Occupancy"
          value={`${occupancyPct}%`}
          hint={`${occupied ?? 0} of ${snap?.rooms.length ?? 0} rooms`}
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
                    disabled={busy === row.name || !row.room}
                    onClick={() => act(row.name, () => checkIn(row.name))}
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
    </div>
  )
}
