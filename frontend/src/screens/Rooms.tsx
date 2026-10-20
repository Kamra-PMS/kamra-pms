/*  Rooms: the big board. Every room as a tile by floor, with what is
    happening in it today. Tap a room for its full story (RoomDrawer);
    Insights shows which rooms sell, earn and get cleaned, and how fast.
    For the desk and housekeeping supervisors; sized for a tablet. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useOutletContext, useSearchParams } from "react-router-dom"
import { BedDouble, Lock, LogIn, LogOut, RefreshCw, Search } from "lucide-react"
import type { ShellContext } from "../AppShell"
import { getRoomsBoard, type BoardRoom, type RoomsBoard } from "../lib/rooms"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "../components/ui/button"
import RoomDrawer, { HK_TONE } from "../components/RoomDrawer"
import RoomInsights from "../components/RoomInsights"
import CheckOutDialog from "../components/CheckOutDialog"
import CheckInDialog from "../components/CheckInDialog"
import RoomChangeDialog from "../components/RoomChangeDialog"

const NO_FLOOR = "__none__"

type StatusFilter =
  | "all"
  | "vacant_ready"
  | "dirty"
  | "occupied"
  | "arriving"
  | "departing"
  | "out"
  | "task"

function matches(r: BoardRoom, f: StatusFilter) {
  switch (f) {
    case "vacant_ready":
      return (
        r.occupancy_status !== "Occupied" &&
        !r.block &&
        ["Clean", "Inspected", "Ready"].includes(r.housekeeping_status)
      )
    case "dirty":
      return r.housekeeping_status === "Dirty"
    case "occupied":
      return r.occupancy_status === "Occupied"
    case "arriving":
      return !!r.arrival
    case "departing":
      return !!r.stay?.departing_today
    case "out":
      return !!r.block || r.housekeeping_status === "Out of Order"
    case "task":
      return !!r.task
    default:
      return true
  }
}

export default function Rooms() {
  const { t } = useT()
  const { refreshKey } = useOutletContext<ShellContext>()
  const [params, setParams] = useSearchParams()
  const view = params.get("view") === "insights" ? "insights" : "board"
  const open = params.get("room")
  const [board, setBoard] = useState<RoomsBoard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [floor, setFloor] = useState("all")
  const [type, setType] = useState("all")
  const [status, setStatus] = useState<StatusFilter>("all")
  // dialogs the drawer hands off to (the drawer hides while one is open)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [moving, setMoving] = useState<{ res: string; number: string } | null>(null)
  const [drawerKey, setDrawerKey] = useState(0)

  const load = useCallback(() => {
    getRoomsBoard()
      .then((b) => {
        setBoard(b)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load, refreshKey])

  const setParam = (k: string, v: string | null) =>
    setParams(
      (p) => {
        const n = new URLSearchParams(p)
        if (v === null) n.delete(k)
        else n.set(k, v)
        return n
      },
      { replace: k !== "room" },
    )

  const rooms = board?.rooms ?? []
  const floorOf = (r: BoardRoom) => (r.floor || "").trim() || NO_FLOOR
  const floors = useMemo(
    () =>
      Array.from(new Set(rooms.map(floorOf))).sort((a, b) =>
        a === NO_FLOOR ? 1 : b === NO_FLOOR ? -1 : a.localeCompare(b, undefined, { numeric: true }),
      ),
    [rooms],
  )
  const shown = rooms.filter(
    (r) =>
      (floor === "all" || floorOf(r) === floor) &&
      (type === "all" || r.room_type === type) &&
      matches(r, status) &&
      (!q.trim() ||
        r.room_number.toLowerCase().includes(q.trim().toLowerCase()) ||
        (r.stay?.guest_name ?? "").toLowerCase().includes(q.trim().toLowerCase()) ||
        (r.arrival?.guest_name ?? "").toLowerCase().includes(q.trim().toLowerCase())),
  )
  const count = (f: StatusFilter) => rooms.filter((r) => matches(r, f)).length
  const chips: { id: StatusFilter; label: string }[] = [
    { id: "all", label: t("All rooms") },
    { id: "vacant_ready", label: t("Ready to sell") },
    { id: "dirty", label: t("Dirty") },
    { id: "occupied", label: t("Occupied") },
    { id: "arriving", label: t("Arriving today") },
    { id: "departing", label: t("Departing today") },
    { id: "out", label: t("Out of service") },
    { id: "task", label: t("Open task") },
  ]
  const floorLabel = (f: string) =>
    f === NO_FLOOR ? t("No floor set") : /floor/i.test(f) ? f : t("Floor {f}", { f })
  const dialogOpen = !!(checkingOut || checkingIn || moving)

  return (
    <div className="min-w-0">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-zinc-900">{t("Rooms")}</h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            {t("Tap a room to change its status, see who is in it, who stayed and who cleaned it.")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div role="tablist" className="flex rounded-lg border border-zinc-200 bg-white p-0.5">
            {(["board", "insights"] as const).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => setParam("view", v === "board" ? null : v)}
                className={cn(
                  "min-h-10 rounded-md px-4 text-sm font-medium",
                  view === v ? "bg-brand-600 text-white" : "text-zinc-600 hover:bg-zinc-50",
                )}
              >
                {v === "board" ? t("Board") : t("Insights")}
              </button>
            ))}
          </div>
          <Button variant="outline" className="min-h-10" onClick={load} aria-label={t("Refresh")}>
            <RefreshCw className="size-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {view === "insights" ? (
        <RoomInsights onOpenRoom={(r) => setParam("room", r)} />
      ) : (
        <>
          <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
            <label className="relative block min-w-0">
              <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t("Room number or guest")}
                aria-label={t("Room number or guest")}
                className="min-h-11 w-full rounded-lg border border-zinc-300 bg-white ps-9 pe-3 text-base"
              />
            </label>
            <select
              value={floor}
              onChange={(e) => setFloor(e.target.value)}
              aria-label={t("Floor")}
              className="min-h-11 w-full min-w-0 rounded-lg border border-zinc-300 bg-white px-3 text-base"
            >
              <option value="all">{t("All floors")}</option>
              {floors.map((f) => (
                <option key={f} value={f}>
                  {floorLabel(f)}
                </option>
              ))}
            </select>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              aria-label={t("Room type")}
              className="min-h-11 w-full min-w-0 rounded-lg border border-zinc-300 bg-white px-3 text-base"
            >
              <option value="all">{t("All room types")}</option>
              {(board?.room_types ?? []).map((rt) => (
                <option key={rt.name} value={rt.name}>
                  {rt.room_type_name}
                </option>
              ))}
            </select>
          </div>
          <div className="mb-4 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <button
                key={c.id}
                onClick={() => setStatus(c.id)}
                aria-pressed={status === c.id}
                className={cn(
                  "min-h-10 rounded-full border px-3 text-sm font-medium",
                  status === c.id
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-400",
                )}
              >
                {c.label}
                <span className="ms-1.5 tabular-nums opacity-75">{count(c.id)}</span>
              </button>
            ))}
          </div>

          {!board ? (
            !error && <p className="text-sm text-zinc-400">{t("Loading…")}</p>
          ) : shown.length === 0 ? (
            <p className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500">
              {t("No room matches these filters.")}
            </p>
          ) : (
            <div className="space-y-5">
              {floors
                .filter((f) => shown.some((r) => floorOf(r) === f))
                .map((f) => (
                  <section key={f} className="min-w-0">
                    <h2 className="mb-2 text-sm font-semibold text-zinc-600">{floorLabel(f)}</h2>
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))] gap-2.5">
                      {shown
                        .filter((r) => floorOf(r) === f)
                        .map((r) => (
                          <RoomTile key={r.name} r={r} onOpen={() => setParam("room", r.name)} />
                        ))}
                    </div>
                  </section>
                ))}
            </div>
          )}
          <Legend />
        </>
      )}

      {open && !dialogOpen && (
        <RoomDrawer
          room={open}
          reloadKey={drawerKey}
          onClose={() => setParam("room", null)}
          onChanged={load}
          onCheckOut={setCheckingOut}
          onCheckIn={setCheckingIn}
          onMove={(res, number) => setMoving({ res, number })}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            setDrawerKey((k) => k + 1)
            load()
          }}
          onOpenReservation={(name) => setCheckingOut(name)}
        />
      )}
      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            setDrawerKey((k) => k + 1)
            load()
          }}
        />
      )}
      {moving && (
        <RoomChangeDialog
          reservation={moving.res}
          currentRoomNumber={moving.number}
          onClose={() => setMoving(null)}
          onMoved={() => {
            setMoving(null)
            setDrawerKey((k) => k + 1)
            load()
          }}
        />
      )}
    </div>
  )
}

function RoomTile({ r, onOpen }: { r: BoardRoom; onOpen: () => void }) {
  const { t } = useT()
  const occupied = r.occupancy_status === "Occupied"
  const out = !!r.block || r.housekeeping_status === "Out of Order"
  const who = r.stay?.surname ?? r.arrival?.surname
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={t("Room {n}", { n: r.room_number })}
      className={cn(
        "flex min-h-[6.5rem] w-full min-w-0 flex-col rounded-xl border-2 p-2.5 text-start transition-transform",
        "hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
        occupied
          ? "border-brand-700 bg-brand-700 text-white"
          : out
            ? "border-rose-400 bg-rose-50 text-rose-900"
            : HK_TONE[r.housekeeping_status],
      )}
    >
      <div className="flex w-full items-start justify-between gap-1">
        <span className="text-xl font-bold leading-none tabular-nums">{r.room_number}</span>
        <span className="flex shrink-0 items-center gap-1">
          {out && <Lock className="size-4" aria-label={t("Out of service")} />}
          {occupied && <BedDouble className="size-4" aria-label={t("Occupied")} />}
        </span>
      </div>
      <div className="mt-1 w-full truncate text-xs opacity-80">{r.room_type_name}</div>
      <div className="mt-auto w-full pt-1">
        {who && <div className="truncate text-sm font-semibold">{who}</div>}
        <div className="flex flex-wrap items-center gap-1">
          <span className="truncate text-[11px] font-medium uppercase tracking-wide opacity-90">
            {r.block ? t("Out of service") : t(r.housekeeping_status)}
          </span>
          {r.stay?.departing_today && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded px-1 text-[10px] font-semibold",
                occupied ? "bg-white/20" : "bg-amber-200 text-amber-900",
              )}
            >
              <LogOut className="size-3" aria-hidden />
              {t("Dep")}
            </span>
          )}
          {r.arrival && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded px-1 text-[10px] font-semibold",
                occupied ? "bg-white/20" : "bg-sky-200 text-sky-900",
              )}
            >
              <LogIn className="size-3" aria-hidden />
              {t("Arr")}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}

function Legend() {
  const { t } = useT()
  const items: [string, string][] = [
    [t("Clean"), "bg-emerald-100 border-emerald-300"],
    [t("Inspected"), "bg-sky-100 border-sky-300"],
    [t("Dirty"), "bg-amber-100 border-amber-300"],
    [t("Out of service"), "bg-rose-100 border-rose-400"],
    [t("Occupied"), "bg-brand-700 border-brand-700"],
  ]
  return (
    <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
      {items.map(([label, cls]) => (
        <span key={label} className="inline-flex items-center gap-1.5">
          <span className={cn("size-3.5 rounded border", cls)} />
          {label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1">
        <LogIn className="size-3.5" /> {t("Arr = arriving today")}
      </span>
      <span className="inline-flex items-center gap-1">
        <LogOut className="size-3.5" /> {t("Dep = leaving today")}
      </span>
    </div>
  )
}
