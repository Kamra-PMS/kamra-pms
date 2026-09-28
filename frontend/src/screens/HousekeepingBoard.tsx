/*  Room Board for the housekeeping supervisor (#99): every room at a
    glance - status, who is in it, who is on it - inside the Housekeeping
    module, not just on the front desk's Today. Status changes go through
    set_housekeeping_status, which checks role, property and DocPerm. */

import { useCallback, useEffect, useState } from "react"
import { BedDouble, LogOut, RefreshCw, User } from "lucide-react"
import { call, getCurrentProperty, setHousekeepingStatus } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"
import { useT } from "../lib/i18n"

type HkStatus = "Clean" | "Dirty" | "Inspected" | "Out of Order"

interface BoardRoom {
  name: string
  room_number: string
  room_type: string
  floor: string | null
  housekeeping_status: HkStatus
  occupancy_status: "Vacant" | "Occupied"
  guest_name: string | null
  due_out: boolean
  task: {
    name: string
    type: string
    status: string
    priority: string
    assignee: string | null
  } | null
}

const STATUSES: HkStatus[] = ["Dirty", "Clean", "Inspected", "Out of Order"]
// an attendant marks rooms Clean / Dirty; passing or blocking a room is the
// supervisor's call - the server enforces the same rule
const ATTENDANT: HkStatus[] = ["Dirty", "Clean"]

const tone: Record<HkStatus, string> = {
  Clean: "border-emerald-300 bg-emerald-50 text-emerald-900",
  Inspected: "border-sky-300 bg-sky-50 text-sky-900",
  Dirty: "border-amber-300 bg-amber-50 text-amber-900",
  "Out of Order": "border-rose-300 bg-rose-50 text-rose-900",
}
const dot: Record<HkStatus, string> = {
  Clean: "bg-emerald-500",
  Inspected: "bg-sky-500",
  Dirty: "bg-amber-500",
  "Out of Order": "bg-rose-500",
}

type Filter = "All" | HkStatus | "Due out" | "Has task"

export default function HousekeepingBoard() {
  const { t } = useT()
  const [rooms, setRooms] = useState<BoardRoom[] | null>(null)
  const [canSupervise, setCanSupervise] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [floor, setFloor] = useState("All")
  const [filter, setFilter] = useState<Filter>("All")

  const load = useCallback(() => {
    call<{ rooms: BoardRoom[]; can_supervise: boolean }>("kamra.api.room_board", {
      property: getCurrentProperty(),
    })
      .then((d) => {
        setRooms(d.rooms)
        setCanSupervise(d.can_supervise)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  async function setStatus(room: string, status: HkStatus) {
    setBusy(room)
    setOpen(null)
    try {
      await setHousekeepingStatus(room, status)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  if (error && !rooms)
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {error}
      </div>
    )
  if (!rooms) return <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>

  const floors = Array.from(new Set(rooms.map((r) => r.floor).filter(Boolean))).sort() as string[]
  const counts = Object.fromEntries(
    STATUSES.map((s) => [s, rooms.filter((r) => r.housekeeping_status === s).length]),
  ) as Record<HkStatus, number>
  const dueOut = rooms.filter((r) => r.due_out).length
  const withTask = rooms.filter((r) => r.task).length
  const shown = rooms.filter(
    (r) =>
      (floor === "All" || r.floor === floor) &&
      (filter === "All" ||
        (filter === "Due out" ? r.due_out : filter === "Has task" ? !!r.task : r.housekeeping_status === filter)),
  )
  const groups = floor === "All" && floors.length ? floors : [floor === "All" ? "" : floor]
  const choices = canSupervise ? STATUSES : ATTENDANT

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">{t("Room Board")}</h1>
          <p className="text-sm text-zinc-500">
            {canSupervise
              ? t("Every room at a glance. Tap a room to set its status.")
              : t("Every room at a glance. You can mark rooms Clean or Dirty.")}
          </p>
        </div>
        <Button variant="outline" onClick={load}>
          <RefreshCw className="size-4" aria-hidden />
          {t("Refresh")}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2" role="toolbar" aria-label={t("Filter rooms")}>
        {(
          [
            ["All", rooms.length, "bg-zinc-400"],
            ...STATUSES.map((s) => [s, counts[s], dot[s]]),
            ["Due out", dueOut, "bg-violet-500"],
            ["Has task", withTask, "bg-zinc-700"],
          ] as [Filter, number, string][]
        ).map(([f, n, d]) => (
          <button
            key={f}
            type="button"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm",
              filter === f
                ? "border-brand-600 bg-brand-50 font-medium text-brand-800"
                : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300",
            )}
          >
            <span className={cn("size-2 rounded-full", d)} aria-hidden />
            {t(f)}
            <span className="tabular-nums text-zinc-400">{n}</span>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("Rooms")}</CardTitle>
          {floors.length > 1 && (
            <div className="flex flex-wrap gap-1">
              {["All", ...floors].map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFloor(f)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs font-medium",
                    floor === f ? "bg-zinc-900 text-white" : "text-zinc-500 hover:bg-zinc-100",
                  )}
                >
                  {f === "All" ? t("All Floors") : t("Floor {f}", { f })}
                </button>
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {shown.length === 0 && (
            <p className="py-6 text-center text-sm text-zinc-400">{t("No rooms match.")}</p>
          )}
          {groups.map((g) => {
            const list = shown.filter((r) => !g || r.floor === g)
            if (!list.length) return null
            return (
              <div key={g || "all"}>
                {g && (
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    {t("Floor {f}", { f: g })}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
                  {list.map((r) => (
                    <div key={r.name} className="relative">
                      <button
                        type="button"
                        disabled={busy === r.name}
                        aria-expanded={open === r.name}
                        onClick={() => setOpen(open === r.name ? null : r.name)}
                        className={cn(
                          "w-full rounded-lg border px-3 py-2.5 text-left transition-colors",
                          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
                          tone[r.housekeeping_status],
                          busy === r.name && "opacity-60",
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-base font-semibold">{r.room_number}</span>
                          <span className="flex items-center gap-1">
                            {r.due_out && (
                              <LogOut className="size-3.5 text-violet-600" aria-label={t("Due out")} />
                            )}
                            {r.occupancy_status === "Occupied" && (
                              <BedDouble className="size-3.5" aria-label={t("Occupied")} />
                            )}
                          </span>
                        </div>
                        <div className="mt-0.5 text-[11px] font-medium uppercase tracking-wide opacity-80">
                          {t(r.housekeeping_status)}
                        </div>
                        {r.guest_name && (
                          <div className="mt-1 truncate text-xs opacity-80">{r.guest_name}</div>
                        )}
                        {r.task && (
                          <div className="mt-1.5 flex items-center gap-1 truncate rounded bg-white/70 px-1.5 py-0.5 text-[11px] text-zinc-700">
                            <User className="size-3 shrink-0" aria-hidden />
                            <span className="truncate">
                              {t(r.task.type)} · {r.task.assignee ?? t("Unassigned")}
                            </span>
                          </div>
                        )}
                      </button>
                      {open === r.name && (
                        <div
                          role="menu"
                          className="absolute inset-x-0 top-full z-10 mt-1 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg"
                        >
                          {choices
                            .filter((s) => s !== r.housekeeping_status)
                            .map((s) => (
                              <button
                                key={s}
                                type="button"
                                role="menuitem"
                                onClick={() => setStatus(r.name, s)}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50"
                              >
                                <span className={cn("size-2 rounded-full", dot[s])} aria-hidden />
                                {t("Mark {status}", { status: t(s) })}
                              </button>
                            ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
