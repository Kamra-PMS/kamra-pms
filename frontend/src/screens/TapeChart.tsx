import { useCallback, useEffect, useMemo, useState } from "react"
import { useOutletContext } from "react-router-dom"
import type { ShellContext } from "../AppShell"
import { ChevronDown, ChevronLeft, ChevronRight, Lock, Sparkles, Star } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"

/** The tape chart: rooms × dates, bookings as bars. Click a bar to act. */

interface TapeBooking {
  name: string
  room: string
  guest_name: string
  status: "Confirmed" | "Checked In"
  check_in_date: string
  check_out_date: string
  is_day_use: 0 | 1
  vip?: 0 | 1
  source?: string
  booking_type?: string
  company?: string | null
  travel_agent?: string | null
  group_booking?: string | null
  planned_check_in_time?: string | null
  planned_check_out_time?: string | null
}

/** "14:30:00" → "14:30" for display. */
const hhmm = (t?: string | null) => (t ? String(t).slice(0, 5) : "")

interface TapeBlock {
  name: string
  reason: string
  from_date: string
  to_date: string
  note?: string | null
}

interface TapeRoom {
  name: string
  room_number: string
  room_type: string
  room_type_name?: string
  floor?: string | null
  housekeeping_status: string
  bookings: TapeBooking[]
  blocks?: TapeBlock[]
}

/** Who is coming - a visible marker on the bar + a label for the tooltip. */
function segment(b: TapeBooking): { label: string; dot: string; vip: boolean } {
  if (b.vip) return { label: "VIP", dot: "bg-amber-300", vip: true }
  if (b.booking_type === "Group" || b.group_booking)
    return { label: "Group", dot: "bg-sky-200", vip: false }
  if (b.booking_type === "Corporate" || b.company)
    return { label: "Corporate", dot: "bg-violet-300", vip: false }
  if (b.travel_agent)
    return { label: "Travel agent", dot: "bg-teal-300", vip: false }
  if (b.source === "OTA")
    return { label: "OTA", dot: "bg-orange-300", vip: false }
  if (b.source === "Walk-in")
    return { label: "Walk-in", dot: "bg-zinc-300", vip: false }
  return { label: b.source || "Direct", dot: "bg-white/70", vip: false }
}

interface PositionCell {
  date: string
  sold: number
  capacity: number
  occupancy: number
  limit: number
  overbooked: boolean
  premium_pct: number
  min_rate: number
}
interface Changeover {
  room: string
  room_number: string
  date: string
  out_res: string
  out_guest: string
  etd: string
  in_res: string
  in_guest: string
  eta: string
}
interface TapeData {
  start: string
  dates: string[]
  rooms: TapeRoom[]
  position: PositionCell[]
  conflicts: Changeover[]
}

interface HourlyBooking extends TapeBooking {
  overnight: 0 | 1
  from_hour?: string
  to_hour?: string
}
interface HourlyRoom {
  name: string
  room_number: string
  room_type: string
  room_type_name?: string
  housekeeping_status: string
  bookings: HourlyBooking[]
}
interface HourlyData {
  date: string
  start_hour: number
  end_hour: number
  rooms: HourlyRoom[]
}
const hhmmToNum = (t?: string) => {
  if (!t) return 0
  const [h, m] = t.split(":").map(Number)
  return h + (m || 0) / 60
}

interface AllocProposal {
  reservation: string
  guest_name: string
  vip: 0 | 1
  room_type_name: string
  suggested_room: string
  room_number: string
  why: string
  needs_review: 0 | 1
}
interface AllocData {
  date: string
  proposals: AllocProposal[]
  unfittable: { reservation: string; guest_name: string; reason: string }[]
}

const DAYS = 14
const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function shiftDate(iso: string, days: number) {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function TapeChart() {
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10))
  const [data, setData] = useState<TapeData | null>(null)
  const [sel, setSel] = useState<TapeBooking | null>(null)
  const [freeRooms, setFreeRooms] = useState<string[]>([])
  const [draft, setDraft] = useState({
    room: "", check_in: "", check_out: "", from_time: "", to_time: "",
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rtFilter, setRtFilter] = useState("")
  const [mode, setMode] = useState<"day" | "hour">("day")
  const [hourly, setHourly] = useState<HourlyData | null>(null)
  const [alloc, setAlloc] = useState<AllocData | null>(null)
  const [allocBusy, setAllocBusy] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem("kamra:tape-collapsed") || "[]"))
    } catch {
      return new Set()
    }
  })
  const toggleGroup = (name: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      localStorage.setItem("kamra:tape-collapsed", JSON.stringify([...next]))
      return next
    })

  const { refreshKey } = useOutletContext<ShellContext>()

  // rooms grouped by room type, honoring the filter (rooms arrive ordered)
  const groups = useMemo(() => {
    const out: { key: string; label: string; rooms: TapeRoom[] }[] = []
    for (const r of data?.rooms ?? []) {
      const label = r.room_type_name || r.room_type
      if (rtFilter && label !== rtFilter) continue
      let g = out.find((x) => x.label === label)
      if (!g) {
        g = { key: r.room_type, label, rooms: [] }
        out.push(g)
      }
      g.rooms.push(r)
    }
    return out
  }, [data, rtFilter])

  const roomTypeNames = useMemo(
    () =>
      Array.from(
        new Set((data?.rooms ?? []).map((r) => r.room_type_name || r.room_type)),
      ),
    [data],
  )

  const load = useCallback(() => {
    if (mode === "day") {
      call<TapeData>("kamra.api.tape_chart", {
        property: getCurrentProperty(), start_date: start, days: DAYS,
      }).then(setData)
    } else {
      call<HourlyData>("kamra.api.tape_chart_hourly", {
        property: getCurrentProperty(), date: start,
      }).then(setHourly)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, refreshKey, mode])

  useEffect(load, [load])

  function openBooking(b: TapeBooking) {
    setSel(b)
    setError(null)
    const hb = b as HourlyBooking
    setDraft({
      room: b.room, check_in: b.check_in_date, check_out: b.check_out_date,
      from_time: hhmm(b.planned_check_in_time) || hb.from_hour || "",
      to_time: hhmm(b.planned_check_out_time) || hb.to_hour || "",
    })
    listResource("Room", {
      fields: ["name"],
      filters: [["property", "=", getCurrentProperty()]],
      orderBy: "room_number asc",
    }).then((r) => setFreeRooms(r.map((x) => x.name)))
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      setSel(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function suggestAlloc() {
    setAllocBusy(true)
    try {
      const d = await call<AllocData>("kamra.allocation.suggest_allocation", {
        property: getCurrentProperty(), date: start,
      })
      setAlloc(d)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setAllocBusy(false)
    }
  }

  async function applyAlloc() {
    if (!alloc) return
    setAllocBusy(true)
    try {
      await call("kamra.allocation.apply_allocation", {
        property: getCurrentProperty(),
        assignments: JSON.stringify(alloc.proposals),
      })
      setAlloc(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setAllocBusy(false)
    }
  }

  const cellW = 64 // px per day

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">Tape chart</h1>
        <select
          className={cn(inputCls, "w-auto py-1.5")}
          value={rtFilter}
          onChange={(e) => setRtFilter(e.target.value)}
          aria-label="Filter by room type"
        >
          <option value="">All room types</option>
          {roomTypeNames.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <div className="inline-flex rounded-lg border border-zinc-200 p-0.5 text-sm">
          {(["day", "hour"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "rounded-md px-2.5 py-1 font-medium transition",
                mode === m
                  ? "bg-brand-50 text-brand-700"
                  : "text-zinc-500 hover:text-zinc-700",
              )}
            >
              {m === "day" ? "Days" : "Hourly"}
            </button>
          ))}
        </div>
        <Button variant="outline" disabled={allocBusy} onClick={suggestAlloc}>
          <Sparkles className="size-4 text-brand-600" />
          {allocBusy ? "Thinking..." : "Auto-assign arrivals"}
        </Button>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="outline" aria-label="Previous"
            onClick={() => setStart(shiftDate(start, mode === "day" ? -7 : -1))}>
            <ChevronLeft className="size-4" />
          </Button>
          <input type="date" className={cn(inputCls, "w-40")} value={start}
            onChange={(e) => setStart(e.target.value)} />
          <Button variant="outline" aria-label="Next"
            onClick={() => setStart(shiftDate(start, mode === "day" ? 7 : 1))}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {mode === "hour" && hourly && (
        <TapeHourly data={hourly} onOpen={openBooking} />
      )}

      {/* back-to-back conflicts: the incoming guest lands before the room frees */}
      {mode === "day" && (data?.conflicts?.length ?? 0) > 0 && (
        <div className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <span className="font-semibold">
            {data!.conflicts.length} changeover conflict{data!.conflicts.length === 1 ? "" : "s"}:
          </span>{" "}
          {data!.conflicts.map((c) => (
            <span key={c.in_res} className="mr-3 whitespace-nowrap">
              Room {c.room_number} on {new Date(c.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} —
              out {c.etd} ({c.out_guest}) / in {c.eta} ({c.in_guest})
            </span>
          ))}
        </div>
      )}

      {mode === "day" && (
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
        <div style={{ minWidth: 130 + DAYS * cellW }}>
          {/* header row */}
          <div className="flex border-b border-zinc-200 bg-zinc-50 text-xs font-medium text-zinc-500">
            <div className="w-[130px] shrink-0 px-3 py-2">Room</div>
            {data?.dates.map((d) => {
              const day = new Date(d)
              const weekend = day.getDay() === 0 || day.getDay() === 6
              return (
                <div key={d} style={{ width: cellW }}
                  className={cn("shrink-0 border-l border-zinc-100 px-1 py-2 text-center",
                    weekend && "bg-brand-50 text-brand-700")}>
                  {day.toLocaleDateString("en-IN", { weekday: "short" })}{" "}
                  <span className="font-semibold">{day.getDate()}</span>
                </div>
              )
            })}
          </div>
          {/* house position: sold/capacity per day, demand premium, overbooking */}
          <div className="flex border-b border-zinc-200 bg-white text-[10px]">
            <div className="w-[130px] shrink-0 px-3 py-1 font-medium uppercase tracking-wide text-zinc-400">
              Position
            </div>
            {data?.position?.map((p) => (
              <div key={p.date} style={{ width: cellW }}
                title={`${p.sold}/${p.capacity} sold (${p.occupancy}%)` +
                  (p.limit > p.capacity ? ` · can sell to ${p.limit} (overbooking)` : "") +
                  (p.premium_pct ? ` · demand premium +${p.premium_pct}%` : "") +
                  (p.min_rate ? ` · hurdle ${cur()}${p.min_rate.toLocaleString(moneyLocale())}` : "")}
                className={cn("shrink-0 border-l border-zinc-100 px-1 py-1 text-center tabular-nums",
                  p.overbooked ? "bg-rose-50 font-bold text-rose-600"
                    : p.occupancy >= 80 ? "bg-emerald-50 font-semibold text-emerald-700"
                      : p.occupancy >= 50 ? "text-amber-600" : "text-zinc-400")}>
                {p.sold}/{p.capacity}
                {p.premium_pct > 0 && <span className="ml-0.5 text-emerald-600">▲</span>}
                {p.overbooked && " OB"}
              </div>
            ))}
          </div>

          {data &&
            groups.map((g) => {
              const isCollapsed = collapsed.has(g.label)
              const booked = g.rooms.filter((r) => r.bookings.length > 0).length
              return (
                <div key={g.key}>
                  <button
                    onClick={() => toggleGroup(g.label)}
                    style={{ minWidth: 130 + DAYS * cellW }}
                    className="flex w-full items-center gap-2 border-b border-zinc-200 bg-zinc-50/80 px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 hover:bg-zinc-100"
                  >
                    <ChevronDown
                      className={cn("size-3.5 transition-transform", isCollapsed && "-rotate-90")}
                      aria-hidden
                    />
                    {g.label}
                    <span className="font-normal normal-case tracking-normal text-zinc-400">
                      {g.rooms.length} rooms · {booked} in use
                    </span>
                  </button>
                  {!isCollapsed &&
                    g.rooms.map((room) => (
                      <div key={room.name} className="relative flex border-b border-zinc-100">
                        <div className="w-[130px] shrink-0 px-3 py-2.5">
                          <span className="text-sm font-semibold">{room.room_number}</span>
                          <span className={cn("ml-1.5 align-middle text-[9px] font-medium uppercase",
                            room.housekeeping_status === "Dirty" ? "text-amber-600"
                              : room.housekeeping_status === "Out of Order" ? "text-rose-600"
                                : "text-zinc-400")}>
                            {room.housekeeping_status}
                          </span>
                        </div>
                        {data.dates.map((d) => (
                          <div key={d} style={{ width: cellW }}
                            className="shrink-0 border-l border-zinc-100" />
                        ))}
                        {/* held-out-of-sale bands (house use, VIP, maintenance) */}
                        {(room.blocks ?? []).map((k) => {
                          const s = Math.max(0,
                            (new Date(k.from_date).getTime() - new Date(data.start).getTime()) / 86_400_000)
                          const e = Math.min(DAYS,
                            (new Date(k.to_date).getTime() - new Date(data.start).getTime()) / 86_400_000)
                          if (e <= 0 || s >= DAYS) return null
                          return (
                            <div key={k.name}
                              style={{
                                left: 130 + s * cellW + 2,
                                width: (e - s) * cellW - 4,
                                backgroundImage:
                                  "repeating-linear-gradient(45deg, #d4d4d8 0 6px, #e4e4e7 6px 12px)",
                              }}
                              className="absolute top-1.5 flex h-8 items-center gap-1 truncate rounded-md border border-zinc-300 px-1.5 text-left text-[11px] font-medium text-zinc-600"
                              title={`${k.reason}${k.note ? ` · ${k.note}` : ""} · ${k.from_date} → ${k.to_date}`}>
                              <Lock className="size-3 shrink-0" aria-hidden />
                              <span className="truncate">{k.reason}</span>
                            </div>
                          )
                        })}
                        {/* booking bars */}
                        {room.bookings.map((b) => {
                          const s = Math.max(0,
                            (new Date(b.check_in_date).getTime() - new Date(data.start).getTime()) / 86_400_000)
                          const rawEnd = (new Date(b.check_out_date).getTime() - new Date(data.start).getTime()) / 86_400_000
                          const e = Math.min(DAYS, b.is_day_use ? s + 1 : rawEnd)
                          if (e <= 0 || s >= DAYS) return null
                          const seg = segment(b)
                          const eta = hhmm(b.planned_check_in_time)
                          const etd = hhmm(b.planned_check_out_time)
                          const inConflict = data.conflicts?.some(
                            (c) => c.in_res === b.name || c.out_res === b.name)
                          return (
                            <button key={b.name}
                              onClick={() => openBooking(b)}
                              style={{ left: 130 + s * cellW + 2, width: (e - s) * cellW - 4 }}
                              className={cn(
                                "absolute top-1.5 flex h-8 items-center gap-1 truncate rounded-md px-1.5 text-left text-xs font-medium text-white",
                                b.status === "Checked In" ? "bg-brand-600 hover:bg-brand-700"
                                  : "bg-sky-500 hover:bg-sky-600",
                                inConflict && "ring-2 ring-rose-500 ring-offset-1",
                              )}
                              title={`${b.guest_name} · ${seg.label} · ${b.check_in_date}${eta ? ` ${eta}` : ""} → ${b.check_out_date}${etd ? ` ${etd}` : ""}` +
                                (inConflict ? " · CHANGEOVER CONFLICT" : "")}>
                              {seg.vip ? (
                                <Star className="size-3 shrink-0 fill-amber-300 text-amber-300" aria-hidden />
                              ) : (
                                <span className={cn("size-2 shrink-0 rounded-full", seg.dot)} aria-hidden />
                              )}
                              <span className="truncate">
                                {eta && <span className="mr-1 font-normal opacity-75">{eta}</span>}
                                {b.guest_name}
                              </span>
                              {etd && (e - s) >= 2 && (
                                <span className="ml-auto shrink-0 font-normal opacity-75">{etd}</span>
                              )}
                            </button>
                          )
                        })}
                      </div>
                    ))}
                </div>
              )
            })}
        </div>
      </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-400">
        <span className="flex items-center gap-1.5">
          <Badge tone="sky">Confirmed</Badge>
          <Badge tone="brand">Checked in</Badge>
        </span>
        <span className="flex items-center gap-1">
          <Star className="size-3 fill-amber-400 text-amber-400" /> VIP
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-violet-400" /> Corporate
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-sky-300" /> Group
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-orange-400" /> OTA
        </span>
        <span className="flex items-center gap-1">
          <Lock className="size-3 text-zinc-500" /> Held (house use / VIP /
          maintenance)
        </span>
        <span>Click a bar to move rooms or change dates.</span>
      </div>

      {alloc && (
        <Sheet
          title="Auto-assign arrivals"
          description={`Suggested room plan for ${alloc.date}`}
          onClose={() => setAlloc(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAlloc(null)}>Close</Button>
              {alloc.proposals.length > 0 && (
                <Button disabled={allocBusy} onClick={applyAlloc}>
                  {allocBusy ? "Assigning..." : `Assign ${alloc.proposals.length} room${alloc.proposals.length === 1 ? "" : "s"}`}
                </Button>
              )}
            </div>
          }
        >
          <div className="space-y-3">
            {alloc.proposals.length === 0 && alloc.unfittable.length === 0 && (
              <p className="text-sm text-zinc-500">
                Every arrival for this day already has a room.
              </p>
            )}
            {alloc.proposals.map((p) => (
              <div key={p.reservation}
                className="flex items-start gap-3 rounded-xl border border-zinc-200 p-3">
                <div className="flex-1">
                  <div className="flex items-center gap-1.5 font-medium">
                    {p.vip === 1 && (
                      <Star className="size-3.5 fill-amber-400 text-amber-400" />
                    )}
                    {p.guest_name}
                    <span className="text-xs font-normal text-zinc-400">
                      · {p.room_type_name}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-zinc-500">{p.why}</p>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold">Room {p.room_number}</div>
                  {p.needs_review === 1 && (
                    <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600">
                      Review
                    </span>
                  )}
                </div>
              </div>
            ))}
            {alloc.unfittable.map((u) => (
              <div key={u.reservation}
                className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                {u.guest_name} - {u.reason}
              </div>
            ))}
            <p className="text-xs text-zinc-400">
              Rooms are matched to each guest's type and preferences. Assigning
              places them now; "Review" flags a choice worth a second look.
            </p>
          </div>
        </Sheet>
      )}

      {sel && (
        <Sheet
          title={sel.guest_name}
          description={`${sel.name} · ${sel.status}`}
          onClose={() => setSel(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSel(null)}>Close</Button>
              {draft.room !== sel.room && (
                <Button disabled={busy}
                  onClick={() => act(() => call("kamra.api.move_reservation",
                    { reservation: sel.name, new_room: draft.room }))}>
                  Move room
                </Button>
              )}
              {(draft.check_in !== sel.check_in_date ||
                draft.check_out !== sel.check_out_date) && (
                <Button disabled={busy}
                  onClick={() => act(() => call("kamra.api.amend_stay",
                    { reservation: sel.name, check_in_date: draft.check_in,
                      check_out_date: draft.check_out }))}>
                  Update stay
                </Button>
              )}
            </div>
          }
        >
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">Room</span>
              <select className={inputCls} value={draft.room}
                onChange={(e) => setDraft({ ...draft, room: e.target.value })}>
                {freeRooms.map((r) => (
                  <option key={r} value={r}>Room {r.split("-").pop()}</option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Check-in</span>
                <input type="date" className={inputCls} value={draft.check_in}
                  onChange={(e) => setDraft({ ...draft, check_in: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Check-out</span>
                <input type="date" className={inputCls} value={draft.check_out}
                  onChange={(e) => setDraft({ ...draft, check_out: e.target.value })} />
              </label>
            </div>
            <div className="rounded-lg border border-zinc-200 p-3">
              <span className="mb-2 block text-sm font-medium text-zinc-600">
                {sel.is_day_use === 1 ? "Day-use hours" : "Arrival / departure times (ETA · ETD)"}
              </span>
              <div className="flex items-end gap-2">
                <input type="time" className={inputCls} value={draft.from_time}
                  onChange={(e) => setDraft({ ...draft, from_time: e.target.value })} />
                <span className="pb-2 text-zinc-400">to</span>
                <input type="time" className={inputCls} value={draft.to_time}
                  onChange={(e) => setDraft({ ...draft, to_time: e.target.value })} />
                <Button variant="outline" disabled={busy}
                  onClick={() => act(() => call("kamra.api.set_stay_times", {
                    reservation: sel.name, eta: draft.from_time,
                    etd: draft.to_time }))}>
                  Set
                </Button>
              </div>
              {sel.is_day_use !== 1 && (
                <p className="mt-1.5 text-xs text-zinc-400">
                  Times drive the house position: back-to-back rooms flag a
                  conflict when the arrival lands before the departure.
                </p>
              )}
            </div>
            <p className="text-xs text-zinc-400">
              Date changes re-price automatically (unless the booking holds a
              manual amount) and the double-booking guard re-checks the room.
            </p>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
          </div>
        </Sheet>
      )}
    </div>
  )
}

/** Single-day, rooms x hours. Day-use bookings sit at their planned times;
 *  overnight stays crossing the day show as a full-width occupied band. */
function TapeHourly({
  data,
  onOpen,
}: {
  data: HourlyData
  onOpen: (b: TapeBooking) => void
}) {
  const hours: number[] = []
  for (let h = data.start_hour; h <= data.end_hour; h++) hours.push(h)
  const span = data.end_hour - data.start_hour || 1
  const hourW = 56
  const gridW = hours.length * hourW

  const left = (t?: string) =>
    ((hhmmToNum(t) - data.start_hour) / span) * gridW
  const width = (from?: string, to?: string) =>
    Math.max(hourW * 0.6, ((hhmmToNum(to) - hhmmToNum(from)) / span) * gridW)

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div style={{ minWidth: 130 + gridW }}>
        <div className="flex border-b border-zinc-200 bg-zinc-50 text-xs font-medium text-zinc-500">
          <div className="w-[130px] shrink-0 px-3 py-2">Room</div>
          {hours.map((h) => (
            <div
              key={h}
              style={{ width: hourW }}
              className="shrink-0 border-l border-zinc-100 px-1 py-2 text-center"
            >
              {String(h).padStart(2, "0")}:00
            </div>
          ))}
        </div>
        {data.rooms.map((room) => (
          <div key={room.name} className="relative flex border-b border-zinc-100">
            <div className="w-[130px] shrink-0 px-3 py-3">
              <span className="text-sm font-semibold">{room.room_number}</span>
              <span className="ml-1.5 text-[9px] uppercase text-zinc-400">
                {room.room_type_name}
              </span>
            </div>
            {hours.map((h) => (
              <div key={h} style={{ width: hourW }} className="shrink-0 border-l border-zinc-100" />
            ))}
            {room.bookings.map((b) => {
              const seg = segment(b)
              if (b.overnight) {
                return (
                  <button
                    key={b.name}
                    onClick={() => onOpen(b)}
                    style={{ left: 130, width: gridW }}
                    className="absolute top-2 flex h-9 items-center gap-1 rounded-md bg-zinc-200/70 px-2 text-left text-xs font-medium text-zinc-600 hover:bg-zinc-300/70"
                    title={`${b.guest_name} · overnight stay`}
                  >
                    {seg.vip && <Star className="size-3 fill-amber-400 text-amber-400" />}
                    <span className="truncate">{b.guest_name} · staying over</span>
                  </button>
                )
              }
              return (
                <button
                  key={b.name}
                  onClick={() => onOpen(b)}
                  style={{ left: 130 + left(b.from_hour) + 2, width: width(b.from_hour, b.to_hour) - 4 }}
                  className={cn(
                    "absolute top-2 flex h-9 items-center gap-1 truncate rounded-md px-1.5 text-left text-xs font-medium text-white",
                    b.status === "Checked In" ? "bg-brand-600 hover:bg-brand-700" : "bg-sky-500 hover:bg-sky-600",
                  )}
                  title={`${b.guest_name} · ${b.from_hour}-${b.to_hour} · day use`}
                >
                  {seg.vip ? (
                    <Star className="size-3 shrink-0 fill-amber-300 text-amber-300" />
                  ) : (
                    <span className={cn("size-2 shrink-0 rounded-full", seg.dot)} />
                  )}
                  <span className="truncate">
                    {b.guest_name} · {b.from_hour}
                  </span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
