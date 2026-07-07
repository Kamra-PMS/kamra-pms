import { useCallback, useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import type { ShellContext } from "../AppShell"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cn } from "../lib/utils"

/** The tape chart: rooms × dates, bookings as bars. Click a bar to act. */

interface TapeBooking {
  name: string
  room: string
  guest_name: string
  status: "Confirmed" | "Checked In"
  check_in_date: string
  check_out_date: string
  is_day_use: 0 | 1
}

interface TapeRoom {
  name: string
  room_number: string
  room_type: string
  housekeeping_status: string
  bookings: TapeBooking[]
}

interface TapeData {
  start: string
  dates: string[]
  rooms: TapeRoom[]
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
  const [draft, setDraft] = useState({ room: "", check_in: "", check_out: "" })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const { refreshKey } = useOutletContext<ShellContext>()

  const load = useCallback(() => {
    call<TapeData>("kamra.api.tape_chart", {
      property: getCurrentProperty(), start_date: start, days: DAYS,
    }).then(setData)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, refreshKey])

  useEffect(load, [load])

  function openBooking(b: TapeBooking) {
    setSel(b)
    setError(null)
    setDraft({ room: b.room, check_in: b.check_in_date, check_out: b.check_out_date })
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

  const cellW = 64 // px per day

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">Tape chart</h1>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="outline" aria-label="Previous week"
            onClick={() => setStart(shiftDate(start, -7))}>
            <ChevronLeft className="size-4" />
          </Button>
          <input type="date" className={cn(inputCls, "w-40")} value={start}
            onChange={(e) => setStart(e.target.value)} />
          <Button variant="outline" aria-label="Next week"
            onClick={() => setStart(shiftDate(start, 7))}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

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

          {data?.rooms.map((room) => (
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
              {/* booking bars */}
              {room.bookings.map((b) => {
                const s = Math.max(0,
                  (new Date(b.check_in_date).getTime() - new Date(data.start).getTime()) / 86_400_000)
                const rawEnd = (new Date(b.check_out_date).getTime() - new Date(data.start).getTime()) / 86_400_000
                const e = Math.min(DAYS, b.is_day_use ? s + 1 : rawEnd)
                if (e <= 0 || s >= DAYS) return null
                return (
                  <button key={b.name}
                    onClick={() => openBooking(b)}
                    style={{ left: 130 + s * cellW + 2, width: (e - s) * cellW - 4 }}
                    className={cn(
                      "absolute top-1.5 h-8 truncate rounded-md px-2 text-left text-xs font-medium text-white",
                      b.status === "Checked In" ? "bg-brand-600 hover:bg-brand-700"
                        : "bg-sky-500 hover:bg-sky-600",
                    )}
                    title={`${b.guest_name} · ${b.check_in_date} → ${b.check_out_date}`}>
                    {b.guest_name}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
      <p className="mt-2 flex gap-3 text-xs text-zinc-400">
        <Badge tone="sky">Confirmed</Badge>
        <Badge tone="brand">Checked in</Badge>
        Click a bar to move rooms or change dates.
      </p>

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
