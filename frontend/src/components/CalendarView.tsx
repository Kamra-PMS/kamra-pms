import { useEffect, useState } from "react"
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react"
import { getCalendar, type CalendarData } from "../lib/api"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import { cn } from "../lib/utils"
import { cur, moneyLocale } from "../lib/money"

const inr = (n: number) =>
  n.toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

function cellTone(available: number, total: number) {
  if (available === 0) return "bg-rose-50 text-rose-700"
  if (available <= Math.max(1, Math.floor(total * 0.25)))
    return "bg-amber-50 text-amber-800"
  return "bg-white text-zinc-700"
}

const DAYS = 14

const iso = (d: Date) => d.toISOString().slice(0, 10)

function shift(startIso: string, byDays: number) {
  const d = new Date(startIso + "T00:00:00")
  d.setDate(d.getDate() + byDays)
  return iso(d)
}

function rangeLabel(dates: string[]) {
  if (!dates.length) return ""
  const f = new Date(dates[0]),
    l = new Date(dates[dates.length - 1])
  const fmt = (d: Date, withYear: boolean) =>
    d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      ...(withYear ? { year: "numeric" } : {}),
    })
  return `${fmt(f, f.getFullYear() !== l.getFullYear())} – ${fmt(l, true)}`
}

export function CalendarView(props: {
  onPick: (roomType: string, date: string) => void
  refreshKey: number
}) {
  const [data, setData] = useState<CalendarData | null>(null)
  const [start, setStart] = useState(() => iso(new Date()))
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    getCalendar(DAYS, start)
      .then(setData)
      .finally(() => setLoading(false))
  }, [props.refreshKey, start])

  if (!data) {
    return <p className="py-8 text-center text-sm text-zinc-400">Loading…</p>
  }

  const dayLabel = (iso: string) => {
    const d = new Date(iso)
    return {
      dow: d.toLocaleDateString("en-IN", { weekday: "short" }),
      day: d.getDate(),
      weekend: d.getDay() === 0 || d.getDay() === 6,
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Availability · {rangeLabel(data.dates)}</CardTitle>
          <span className="text-xs text-zinc-400">
            Click a cell to start a booking
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            aria-label="Previous 14 days"
            onClick={() => setStart((s) => shift(s, -DAYS))}
          >
            <ChevronLeft className="size-4" aria-hidden />
          </Button>
          <Button
            variant="outline"
            disabled={start === iso(new Date())}
            onClick={() => setStart(iso(new Date()))}
          >
            <CalendarDays className="size-4" aria-hidden /> Today
          </Button>
          <input
            type="date"
            aria-label="Jump to date"
            className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
            value={start}
            onChange={(e) => e.target.value && setStart(e.target.value)}
          />
          <Button
            variant="outline"
            aria-label="Next 14 days"
            onClick={() => setStart((s) => shift(s, DAYS))}
          >
            <ChevronRight className="size-4" aria-hidden />
          </Button>
        </div>
      </CardHeader>
      <CardContent className={cn(loading && "opacity-60 transition-opacity")}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white pr-3 text-left text-xs font-medium text-zinc-500">
                  Room type
                </th>
                {data.dates.map((d) => {
                  const l = dayLabel(d)
                  const isToday = d === iso(new Date())
                  return (
                    <th
                      key={d}
                      className={cn(
                        "min-w-14 px-1 pb-2 text-center text-xs font-medium",
                        l.weekend ? "text-brand-700" : "text-zinc-500",
                        isToday && "rounded-t-md bg-brand-50",
                      )}
                    >
                      <div>{l.dow}</div>
                      <div className="text-sm font-semibold">{l.day}</div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {data.room_types.map((rt) => (
                <tr key={rt.room_type}>
                  <td className="sticky left-0 whitespace-nowrap bg-white py-1 pr-3 font-medium">
                    {rt.room_type_name}
                    <span className="ml-1 text-xs font-normal text-zinc-400">
                      ×{rt.total_rooms}
                    </span>
                  </td>
                  {rt.cells.map((c) => (
                    <td key={c.date} className="p-0.5">
                      <button
                        onClick={() => props.onPick(rt.room_type, c.date)}
                        disabled={c.available === 0}
                        title={`${rt.room_type_name} · ${c.date} · ${c.available} left · ${cur()}${inr(c.rate)}`}
                        className={cn(
                          "w-full rounded-md border border-zinc-200 px-1 py-1.5 text-center transition-colors",
                          "hover:border-brand-600 focus-visible:outline-2 focus-visible:outline-brand-600",
                          "disabled:cursor-not-allowed",
                          cellTone(c.available, rt.total_rooms),
                        )}
                      >
                        <div className="text-sm font-semibold leading-none">
                          {c.available}
                        </div>
                        <div className="mt-0.5 text-[10px] leading-none opacity-70">
                          {cur()}{inr(c.rate)}
                        </div>
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-zinc-400">
          Number = rooms available · price = 2-adult nightly rate with seasons
          applied. Weekend columns in green.
        </p>
      </CardContent>
    </Card>
  )
}
