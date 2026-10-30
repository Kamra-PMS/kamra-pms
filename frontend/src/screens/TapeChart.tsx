import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useOutletContext } from "react-router-dom"
import type { ShellContext } from "../AppShell"
import {
  ArrowLeftRight, CalendarRange, ChevronDown, ChevronLeft, ChevronRight, ExternalLink,
  Lock, LogIn, LogOut, Sparkles, Star,
} from "lucide-react"
import { amendStay, amendStayPreview, call, getCurrentProperty, type RepricePreview } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate, uiDateLocale } from "../lib/i18n"
import CheckOutDialog from "../components/CheckOutDialog"
import CheckInDialog from "../components/CheckInDialog"
import RoomChangeDialog from "../components/RoomChangeDialog"


/** The tape chart: rooms × dates, bookings as bars. Click a bar to open the
 *  stay panel (move room, change dates, check in / out); with a mouse, drag a
 *  bar to another room or drag its ends to change dates. Every change goes
 *  through a confirm step and the server's own preview / guard. */

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

/** Today on this device's calendar (YYYY-MM-DD). */
function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

function shiftDate(iso: string, days: number) {
  const d = new Date(iso)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

/** Whole days from `a` to `b` (YYYY-MM-DD). */
const dayDiff = (a: string, b: string) =>
  Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000)

type DragMode = "move" | "start" | "end"
interface Drag {
  b: TapeBooking
  mode: DragMode
  x0: number
  y0: number
  dy: number
  days: number
  room: string
  active: boolean
}

export default function TapeChart() {
  const { t, tn } = useT()
  const [start, setStart] = useState(todayIso())
  const [data, setData] = useState<TapeData | null>(null)
  const [sel, setSel] = useState<TapeBooking | null>(null)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  // the room move dialog (price preview + reason), from the panel or a drop
  const [moving, setMoving] = useState<{
    reservation: string
    roomNumber: string | null
    initialRoom?: string
  } | null>(null)
  const [draft, setDraft] = useState({
    check_in: "", check_out: "", from_time: "", to_time: "",
  })
  const [datesOpen, setDatesOpen] = useState(false)
  const [datePreview, setDatePreview] = useState<RepricePreview | null>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const dragRef = useRef<Drag | null>(null)
  const suppressClick = useRef(false)
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

  const { refreshKey, canBook, openBooking: newBooking } = useOutletContext<ShellContext>()

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

  /** Open the stay panel. `dates` pre-fills Change dates (a dragged bar). */
  function openBooking(b: TapeBooking, dates?: { check_in: string; check_out: string }) {
    setSel(b)
    setError(null)
    setDatePreview(null)
    setDatesOpen(!!dates)
    const hb = b as HourlyBooking
    setDraft({
      check_in: dates?.check_in ?? b.check_in_date,
      check_out: dates?.check_out ?? b.check_out_date,
      from_time: hhmm(b.planned_check_in_time) || hb.from_hour || "",
      to_time: hhmm(b.planned_check_out_time) || hb.to_hour || "",
    })
  }

  const roomNumber = (room: string) =>
    data?.rooms.find((r) => r.name === room)?.room_number ??
    hourly?.rooms.find((r) => r.name === room)?.room_number ?? null

  const datesChanged = !!sel &&
    (draft.check_in !== sel.check_in_date || draft.check_out !== sel.check_out_date)
  const datesValid = !!draft.check_in && !!draft.check_out && draft.check_in < draft.check_out

  // new dates re-price the stay: show the server's preview before the desk
  // confirms; amend_stay refuses a changed total without confirm_price
  useEffect(() => {
    setDatePreview(null)
    if (!sel || !datesOpen || !datesChanged || !datesValid) return
    let live = true
    setError(null)
    amendStayPreview(sel.name, draft.check_in, draft.check_out)
      .then((p) => live && setDatePreview(p))
      .catch((e) => live && setError(serverError(e)))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, datesOpen, draft.check_in, draft.check_out])

  const money = (n: number) =>
    `${cur()}${Math.abs(Math.round(n)).toLocaleString(moneyLocale())}`

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

  /* Drag (mouse / pen only; a tap or click opens the panel). Dropping on
     another room's row opens the room move dialog with that room picked;
     dragging the bar sideways or its ends opens Change dates with the new
     dates filled in. Nothing changes until the desk confirms there. */
  function beginDrag(e: React.PointerEvent, b: TapeBooking, mode: DragMode) {
    if (e.pointerType === "touch" || e.button !== 0) return
    e.stopPropagation()
    dragRef.current = {
      b, mode, x0: e.clientX, y0: e.clientY, dy: 0, days: 0, room: b.room, active: false,
    }
  }

  useEffect(() => {
    function onMove(e: PointerEvent) {
      const d = dragRef.current
      if (!d) return
      const dx = e.clientX - d.x0
      const dy = e.clientY - d.y0
      if (!d.active && Math.hypot(dx, dy) < 6) return
      const rtl = document.documentElement.dir === "rtl"
      let days = Math.round((rtl ? -dx : dx) / cellW)
      let room = d.b.room
      const nights = Math.max(1, dayDiff(d.b.check_in_date, d.b.check_out_date))
      if (d.mode === "move") {
        const row = document.elementFromPoint(e.clientX, e.clientY)
          ?.closest<HTMLElement>("[data-room]")
        if (row?.dataset.room) room = row.dataset.room
        // a room move keeps the dates; an in-house guest's arrival is fixed,
        // and a day-use booking's hours are set in the panel
        if (room !== d.b.room || d.b.status === "Checked In" || d.b.is_day_use) days = 0
      } else if (d.mode === "start") {
        days = Math.min(days, nights - 1)
      } else {
        days = Math.max(days, 1 - nights)
      }
      const next = { ...d, dy, days, room, active: true }
      dragRef.current = next
      setDrag(next)
    }
    function onUp() {
      const d = dragRef.current
      dragRef.current = null
      setDrag(null)
      if (!d?.active) return
      // the click that follows this pointerup must not also open the panel
      suppressClick.current = true
      window.setTimeout(() => (suppressClick.current = false), 0)
      if (d.mode === "move" && d.room !== d.b.room) {
        setMoving({
          reservation: d.b.name,
          roomNumber: roomNumber(d.b.room),
          initialRoom: d.room,
        })
        return
      }
      if (!d.days) return
      const ci = d.mode === "end" ? d.b.check_in_date : shiftDate(d.b.check_in_date, d.days)
      const co = d.mode === "start" ? d.b.check_out_date : shiftDate(d.b.check_out_date, d.days)
      openBooking(d.b, { check_in: ci, check_out: co })
    }
    function onCancel() {
      dragRef.current = null
      setDrag(null)
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    window.addEventListener("pointercancel", onCancel)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      window.removeEventListener("pointercancel", onCancel)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  async function confirmDates() {
    if (!sel || !datePreview) return
    await act(() => amendStay(sel.name, draft.check_in, draft.check_out,
      datePreview.needs_confirmation ? 1 : 0))
  }

  const checkInDue = !!sel && sel.status === "Confirmed" && sel.check_in_date <= todayIso()

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">{t("Tape chart")}</h1>
        <select
          className={cn(inputCls, "w-auto py-1.5")}
          value={rtFilter}
          onChange={(e) => setRtFilter(e.target.value)}
          aria-label={t("Filter by room type")}
        >
          <option value="">{t("All room types")}</option>
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
              {m === "day" ? t("Days") : t("Hourly")}
            </button>
          ))}
        </div>
        <Button variant="outline" disabled={allocBusy} onClick={suggestAlloc}>
          <Sparkles className="size-4 text-brand-600" />
          {allocBusy ? t("Thinking...") : t("Auto-assign arrivals")}
        </Button>
        <div className="ms-auto flex items-center gap-1">
          <Button variant="outline" aria-label={t("Previous")}
            onClick={() => setStart(shiftDate(start, mode === "day" ? -7 : -1))}>
            <ChevronLeft className="size-4 rtl:rotate-180" />
          </Button>
          <input type="date" className={cn(inputCls, "w-40")} value={start}
            onChange={(e) => setStart(e.target.value)} />
          <Button variant="outline" aria-label={t("Next")}
            onClick={() => setStart(shiftDate(start, mode === "day" ? 7 : 1))}>
            <ChevronRight className="size-4 rtl:rotate-180" />
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
            {t("{n} changeover conflict{s}", {
              n: data!.conflicts.length,
              s: data!.conflicts.length === 1 ? "" : "s",
            })}:
          </span>{" "}
          {data!.conflicts.map((c) => (
            <span key={c.in_res} className="me-3 whitespace-nowrap">
              {t("Room {room} on {date}: out {etd} ({out}) / in {eta} ({in})", {
                room: c.room_number,
                date: new Date(c.date).toLocaleDateString(uiDateLocale(moneyLocale()), { day: "numeric", month: "short" }),
                etd: c.etd, out: c.out_guest, eta: c.eta, in: c.in_guest,
              })}
            </span>
          ))}
        </div>
      )}

      {mode === "day" && (
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
        <div style={{ minWidth: 130 + DAYS * cellW }}>
          {/* header row */}
          <div className="flex border-b border-zinc-200 bg-zinc-50 text-xs font-medium text-zinc-500">
            <div className="w-[130px] shrink-0 px-3 py-2">{t("Room")}</div>
            {data?.dates.map((d) => {
              const day = new Date(d)
              const weekend = day.getDay() === 0 || day.getDay() === 6
              return (
                <div key={d} style={{ width: cellW }}
                  className={cn("shrink-0 border-l border-zinc-100 px-1 py-2 text-center",
                    weekend && "bg-brand-50 text-brand-700")}>
                  {day.toLocaleDateString(uiDateLocale(moneyLocale()), { weekday: "short" })}{" "}
                  <span className="font-semibold">{day.getDate()}</span>
                </div>
              )
            })}
          </div>
          {/* house position: sold/capacity per day, demand premium, overbooking */}
          <div className="flex border-b border-zinc-200 bg-white text-[10px]">
            <div className="w-[130px] shrink-0 px-3 py-1 font-medium uppercase tracking-wide text-zinc-400">
              {t("Position")}
            </div>
            {data?.position?.map((p) => (
              <div key={p.date} style={{ width: cellW }}
                title={[
                  t("{sold}/{capacity} sold ({occupancy}%)", { sold: p.sold, capacity: p.capacity, occupancy: p.occupancy }),
                  p.limit > p.capacity ? t("can sell to {limit} (overbooking)", { limit: p.limit }) : null,
                  p.premium_pct ? t("demand premium +{premium}%", { premium: p.premium_pct }) : null,
                  p.min_rate ? t("hurdle {amount}", { amount: `${cur()}${p.min_rate.toLocaleString(moneyLocale())}` }) : null,
                ].filter(Boolean).join(" · ")}
                className={cn("shrink-0 border-l border-zinc-100 px-1 py-1 text-center tabular-nums",
                  p.overbooked ? "bg-rose-50 font-bold text-rose-600"
                    : p.occupancy >= 80 ? "bg-emerald-50 font-semibold text-emerald-700"
                      : p.occupancy >= 50 ? "text-amber-600" : "text-zinc-400")}>
                {p.sold}/{p.capacity}
                {p.premium_pct > 0 && <span className="ms-0.5 text-emerald-600">▲</span>}
                {p.overbooked && translate(" OB")}
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
                    className="flex w-full items-center gap-2 border-b border-zinc-200 bg-zinc-50/80 px-3 py-1.5 text-start text-xs font-semibold uppercase tracking-wide text-zinc-600 hover:bg-zinc-100"
                  >
                    <ChevronDown
                      className={cn("size-3.5 transition-transform", isCollapsed && "-rotate-90 rtl:rotate-90")}
                      aria-hidden
                    />
                    {translate(g.label)}
                    <span className="font-normal normal-case tracking-normal text-zinc-400">
                      {t("{rooms} rooms · {booked} in use", {
                        rooms: g.rooms.length,
                        booked,
                      })}
                    </span>
                  </button>
                  {!isCollapsed &&
                    g.rooms.map((room) => (
                      <div key={room.name} data-room={room.name}
                        className={cn("relative flex border-b border-zinc-100",
                          drag?.active && drag.room === room.name && drag.room !== drag.b.room &&
                            "bg-brand-50 outline-2 -outline-offset-2 outline-brand-600/40")}>
                        <div className="w-[130px] shrink-0 px-3 py-2.5">
                          <span className="text-sm font-semibold">{room.room_number}</span>
                          <span className={cn("ms-1.5 align-middle text-[9px] font-medium uppercase",
                            room.housekeeping_status === "Dirty" ? "text-amber-600"
                              : room.housekeeping_status === "Out of Order" ? "text-rose-600"
                                : "text-zinc-400")}>
                            {t(room.housekeeping_status)}
                          </span>
                        </div>
                        {/* vacant cell: bars and blocks sit on top, so a click here is a free night */}
                        {data.dates.map((d) => canBook && d >= todayIso() ? (
                          <button key={d} type="button" style={{ width: cellW }}
                            aria-label={t("New booking")}
                            onClick={() => newBooking({ room_type: room.room_type, room: room.name,
                              room_number: room.room_number, date: d })}
                            className="shrink-0 border-l border-zinc-100 hover:bg-brand-50" />
                        ) : (
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
                                insetInlineStart: 130 + s * cellW + 2,
                                width: (e - s) * cellW - 4,
                                backgroundImage:
                                  "repeating-linear-gradient(45deg, #d4d4d8 0 6px, #e4e4e7 6px 12px)",
                              }}
                              className="absolute top-1.5 flex h-8 items-center gap-1 truncate rounded-md border border-zinc-300 px-1.5 text-start text-[11px] font-medium text-zinc-600"
                              title={`${t(k.reason)}${k.note ? ` · ${k.note}` : ""} · ${k.from_date} → ${k.to_date}`}>
                              <Lock className="size-3 shrink-0" aria-hidden />
                              <span className="truncate">{k.reason}</span>
                            </div>
                          )
                        })}
                        {/* booking bars */}
                        {room.bookings.map((b) => {
                          const dd = drag?.active && drag.b.name === b.name ? drag : null
                          let s0 = dayDiff(data.start, b.check_in_date)
                          let e0 = b.is_day_use ? s0 + 1 : dayDiff(data.start, b.check_out_date)
                          // live preview of the drag: sideways / edges snap to whole days
                          if (dd?.mode === "move") { s0 += dd.days; e0 += dd.days }
                          if (dd?.mode === "start") s0 += dd.days
                          if (dd?.mode === "end") e0 += dd.days
                          const s = Math.max(0, s0)
                          const e = Math.min(DAYS, e0)
                          if (e <= 0 || s >= DAYS) return null
                          const seg = segment(b)
                          const eta = hhmm(b.planned_check_in_time)
                          const etd = hhmm(b.planned_check_out_time)
                          const inConflict = data.conflicts?.some(
                            (c) => c.in_res === b.name || c.out_res === b.name)
                          const roomDrop = dd?.mode === "move" && dd.room !== b.room
                          const resizable = !b.is_day_use
                          return (
                            <button key={b.name}
                              type="button"
                              data-stay={b.name}
                              onPointerDown={(ev) => beginDrag(ev, b, "move")}
                              onClick={() => {
                                if (suppressClick.current) return
                                openBooking(b)
                              }}
                              style={{
                                insetInlineStart: 130 + s * cellW + 2,
                                width: Math.max(8, (e - s) * cellW - 4),
                                transform: roomDrop ? `translateY(${dd!.dy}px)` : undefined,
                              }}
                              className={cn(
                                "group absolute top-1.5 flex h-8 cursor-pointer select-none items-center gap-1 truncate rounded-md px-1.5 text-start text-xs font-medium text-white",
                                b.status === "Checked In" ? "bg-brand-600 hover:bg-brand-700"
                                  : "bg-sky-500 hover:bg-sky-600",
                                inConflict && "ring-2 ring-rose-500 ring-offset-1",
                                dd && "pointer-events-none z-20 cursor-grabbing opacity-90 shadow-lg ring-2 ring-white",
                              )}
                              title={(`${b.guest_name} · ${t(seg.label)} · ${b.check_in_date}${eta ? ` ${eta}` : ""} → ${b.check_out_date}${etd ? ` ${etd}` : ""}` +
                                (inConflict ? ` · ${t("CHANGEOVER CONFLICT")}` : ""))}>
                              {/* drag handles: arrival (not once checked in) and departure */}
                              {resizable && b.status === "Confirmed" && s0 >= 0 && (
                                <span aria-hidden data-handle="start"
                                  onPointerDown={(ev) => beginDrag(ev, b, "start")}
                                  className="absolute inset-y-0 start-0 w-2 cursor-ew-resize rounded-s-md group-hover:bg-white/30" />
                              )}
                              {resizable && e0 <= DAYS && (
                                <span aria-hidden data-handle="end"
                                  onPointerDown={(ev) => beginDrag(ev, b, "end")}
                                  className="absolute inset-y-0 end-0 w-2 cursor-ew-resize rounded-e-md group-hover:bg-white/30" />
                              )}
                              {seg.vip ? (
                                <Star className="size-3 shrink-0 fill-amber-300 text-amber-300" aria-hidden />
                              ) : (
                                <span className={cn("size-2 shrink-0 rounded-full", seg.dot)} aria-hidden />
                              )}
                              <span className="truncate">
                                {eta && <span className="me-1 font-normal opacity-75">{eta}</span>}
                                {b.guest_name}
                              </span>
                              {etd && (e - s) >= 2 && (
                                <span className="ms-auto shrink-0 font-normal opacity-75">{etd}</span>
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
          <Badge tone="sky">{t("Confirmed")}</Badge>
          <Badge tone="brand">{t("Checked in")}</Badge>
        </span>
        <span className="flex items-center gap-1">
          <Star className="size-3 fill-amber-400 text-amber-400" /> {t("VIP")}
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-violet-400" /> {t("Corporate")}
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-sky-300" /> {t("Group")}
        </span>
        <span className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-orange-400" /> {t("OTA")}
        </span>
        <span className="flex items-center gap-1">
          <Lock className="size-3 text-zinc-500" /> {t("Held (house use / VIP / maintenance)")}
        </span>
        <span>
          {mode === "day"
            ? t("Click a bar to move the room, change dates, check in or check out. With a mouse, drag a bar to another room or drag its ends to change dates.")
            : t("Click a bar to move the room, change dates, check in or check out.")}
        </span>
      </div>

      {alloc && (
        <Sheet
          title={t("Auto-assign arrivals")}
          description={t("Suggested room plan for {date}", { date: alloc.date })}
          onClose={() => setAlloc(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAlloc(null)}>{t("Close")}</Button>
              {alloc.proposals.length > 0 && (
                <Button disabled={allocBusy} onClick={applyAlloc}>
                  {allocBusy
                    ? t("Assigning...")
                    : tn(
                        alloc.proposals.length,
                        "Assign {n} room",
                        "Assign {n} rooms",
                      )}
                </Button>
              )}
            </div>
          }
        >
          <div className="space-y-3">
            {alloc.proposals.length === 0 && alloc.unfittable.length === 0 && (
              <p className="text-sm text-zinc-500">
                {t("Every arrival for this day already has a room.")}
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
                  <p className="mt-0.5 text-xs text-zinc-500">{translate(p.why)}</p>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold">{t("Room {n}", { n: p.room_number })}</div>
                  {p.needs_review === 1 && (
                    <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600">
                      {t("Review")}
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
              {t("Rooms are matched to each guest's type and preferences. Assigning places them now; \"Review\" flags a choice worth a second look.")}
            </p>
          </div>
        </Sheet>
      )}

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
      {moving && (
        <RoomChangeDialog
          reservation={moving.reservation}
          currentRoomNumber={moving.roomNumber}
          initialRoom={moving.initialRoom}
          onClose={() => setMoving(null)}
          onMoved={() => {
            setSel(null)
            load()
          }}
        />
      )}
      {sel && (
        <Sheet
          title={translate(sel.guest_name)}
          description={(`${sel.name} · ${t(sel.status)}`)}
          onClose={() => setSel(null)}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link to={`/reservations?q=${encodeURIComponent(sel.name)}`}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
                <ExternalLink className="size-4" aria-hidden />
                {t("Open reservation")}
              </Link>
              <Button variant="outline" onClick={() => setSel(null)}>{t("Close")}</Button>
            </div>
          }
        >
          <div className="space-y-4">
            {/* the stay at a glance */}
            <dl className="grid grid-cols-3 gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm">
              <div>
                <dt className="text-xs text-zinc-500">{t("Room")}</dt>
                <dd className="font-semibold">{roomNumber(sel.room) ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t("Check-in")}</dt>
                <dd className="font-semibold tabular-nums">{sel.check_in_date}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t("Check-out")}</dt>
                <dd className="font-semibold tabular-nums">{sel.check_out_date}</dd>
              </div>
            </dl>

            {/* what the desk can do with it - always visible */}
            <div className="grid grid-cols-2 gap-2" role="group" aria-label={t("Stay actions")}>
              <Button variant="outline" disabled={busy} className="justify-start"
                onClick={() => setMoving({ reservation: sel.name, roomNumber: roomNumber(sel.room) })}>
                <ArrowLeftRight className="size-4" aria-hidden />
                {t("Move room")}
              </Button>
              <Button variant="outline" disabled={busy} aria-expanded={datesOpen}
                className={cn("justify-start", datesOpen && "border-brand-600 bg-brand-50 text-brand-700")}
                onClick={() => {
                  setDatesOpen(!datesOpen)
                  setError(null)
                  setDraft({ ...draft, check_in: sel.check_in_date, check_out: sel.check_out_date })
                }}>
                <CalendarRange className="size-4" aria-hidden />
                {t("Change dates")}
              </Button>
              {checkInDue && (
                <Button className="justify-start" onClick={() => {
                  setCheckingIn(sel.name)
                  setSel(null)
                }}>
                  <LogIn className="size-4" aria-hidden />
                  {t("Check in")}
                </Button>
              )}
              {sel.status === "Checked In" && (
                <Button className="justify-start" onClick={() => {
                  setCheckingOut(sel.name)
                  setSel(null)
                }}>
                  <LogOut className="size-4" aria-hidden />
                  {t("Check out")}
                </Button>
              )}
            </div>
            {sel.status === "Confirmed" && !checkInDue && (
              <p className="text-xs text-zinc-500">
                {t("Check-in opens on the arrival date ({date}).", { date: sel.check_in_date })}
              </p>
            )}

            {datesOpen && (
              <div className="space-y-3 rounded-lg border border-brand-600/30 p-3">
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Check-in")}</span>
                    <input type="date" className={inputCls} value={draft.check_in}
                      disabled={sel.status === "Checked In"}
                      onChange={(e) => setDraft({ ...draft, check_in: e.target.value })} />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Check-out")}</span>
                    <input type="date" className={inputCls} value={draft.check_out}
                      min={draft.check_in}
                      onChange={(e) => setDraft({ ...draft, check_out: e.target.value })} />
                  </label>
                </div>
                {!datesChanged ? (
                  <p className="text-xs text-zinc-500">{t("Pick the new dates.")}</p>
                ) : !datesValid ? (
                  <p className="text-xs text-rose-600">{t("Check-out must be after check-in.")}</p>
                ) : !datePreview ? (
                  !error && <p className="text-xs text-zinc-400">{t("Checking price")}</p>
                ) : datePreview.difference === 0 ? (
                  <p className="text-sm text-zinc-600">
                    {t("{n} nights. No change to the price.", { n: dayDiff(draft.check_in, draft.check_out) })}
                  </p>
                ) : (
                  <p className={cn("text-sm", datePreview.difference > 0 ? "text-amber-700" : "text-emerald-700")}>
                    {datePreview.difference > 0
                      ? t("{n} nights. Stay total {from} to {to} (+{amt}).", {
                          n: dayDiff(draft.check_in, draft.check_out),
                          from: money(datePreview.current_amount),
                          to: money(datePreview.new_amount),
                          amt: money(datePreview.difference),
                        })
                      : t("{n} nights. Stay total {from} to {to} (-{amt}).", {
                          n: dayDiff(draft.check_in, draft.check_out),
                          from: money(datePreview.current_amount),
                          to: money(datePreview.new_amount),
                          amt: money(datePreview.difference),
                        })}
                  </p>
                )}
                {datesChanged && datesValid && datePreview?.charged_nights && (
                  <p className="text-xs text-zinc-500">
                    {datePreview.charged_nights.credit_total < 0
                      ? t("Nights already charged keep their line; Kamra credits {amt} for the lower rate.", {
                          amt: money(-datePreview.charged_nights.credit_total),
                        })
                      : datePreview.charged_nights.kept_difference > 0
                        ? t("Nights already charged keep their rate; difference {amt} can be given as an allowance.", {
                            amt: money(datePreview.charged_nights.kept_difference),
                          })
                        : t("Nights already charged keep their rate.")}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <Button variant="ghost" onClick={() => {
                    setDatesOpen(false)
                    setError(null)
                    setDraft({ ...draft, check_in: sel.check_in_date, check_out: sel.check_out_date })
                  }}>
                    {t("Cancel")}
                  </Button>
                  <Button disabled={busy || !datesChanged || !datesValid || !datePreview}
                    onClick={confirmDates}>
                    {datePreview?.needs_confirmation ? t("Confirm new dates and price") : t("Confirm new dates")}
                  </Button>
                </div>
              </div>
            )}

            <div className="rounded-lg border border-zinc-200 p-3">
              <span className="mb-2 block text-sm font-medium text-zinc-600">
                {sel.is_day_use === 1 ? t("Day-use hours") : t("Arrival / departure times (ETA · ETD)")}
              </span>
              <div className="flex items-end gap-2">
                <input type="time" className={inputCls} value={draft.from_time}
                  onChange={(e) => setDraft({ ...draft, from_time: e.target.value })} />
                <span className="pb-2 text-zinc-400">{t("to")}</span>
                <input type="time" className={inputCls} value={draft.to_time}
                  onChange={(e) => setDraft({ ...draft, to_time: e.target.value })} />
                <Button variant="outline" disabled={busy}
                  onClick={() => act(() => call("kamra.api.set_stay_times", {
                    reservation: sel.name, eta: draft.from_time,
                    etd: draft.to_time }))}>
                  {t("Set")}
                </Button>
              </div>
              {sel.is_day_use !== 1 && (
                <p className="mt-1.5 text-xs text-zinc-400">
                  {t("Times drive the house position: back-to-back rooms flag a conflict when the arrival lands before the departure.")}
                </p>
              )}
            </div>
            <p className="text-xs text-zinc-400">
              {t("Date changes re-price automatically (unless the booking holds a manual amount) and the double-booking guard re-checks the room.")}
            </p>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {translate(error)}
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
  const { t } = useT()
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
          <div className="w-[130px] shrink-0 px-3 py-2">{t("Room")}</div>
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
              <span className="ms-1.5 text-[9px] uppercase text-zinc-400">
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
                    style={{ insetInlineStart: 130, width: gridW }}
                    className="absolute top-2 flex h-9 items-center gap-1 rounded-md bg-zinc-200/70 px-2 text-start text-xs font-medium text-zinc-600 hover:bg-zinc-300/70"
                    title={(`${b.guest_name} · ${t("overnight stay")}`)}
                  >
                    {seg.vip && <Star className="size-3 fill-amber-400 text-amber-400" />}
                    <span className="truncate">{b.guest_name} · {t("staying over")}</span>
                  </button>
                )
              }
              return (
                <button
                  key={b.name}
                  onClick={() => onOpen(b)}
                  style={{ insetInlineStart: 130 + left(b.from_hour) + 2, width: width(b.from_hour, b.to_hour) - 4 }}
                  className={cn(
                    "absolute top-2 flex h-9 items-center gap-1 truncate rounded-md px-1.5 text-start text-xs font-medium text-white",
                    b.status === "Checked In" ? "bg-brand-600 hover:bg-brand-700" : "bg-sky-500 hover:bg-sky-600",
                  )}
                  title={translate("{v0} · {v1}-{v2} · day use", { v0: String(b.guest_name), v1: String(b.from_hour), v2: String(b.to_hour) })}
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
