import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import {
  venueCalendar,
  type VenueBookingCell,
  type VenueCalendarData,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"

const DAYS = 14

const STATUS: Record<string, string> = {
  Enquiry: "bg-amber-100 text-amber-800 border-amber-200",
  Confirmed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  Completed: "bg-zinc-100 text-zinc-600 border-zinc-200",
  Cancelled: "bg-rose-100 text-rose-700 border-rose-200 line-through",
}

const inr = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

function shift(date: string, by: number) {
  const d = new Date(date + "T00:00:00")
  d.setDate(d.getDate() + by)
  return d.toISOString().slice(0, 10)
}
const dow = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" })
const dom = (d: string) => d.slice(8, 10)
const today = new Date().toISOString().slice(0, 10)

function Booking({ b }: { b: VenueBookingCell }) {
  return (
    <div
      className={
        "mb-1 rounded-md border px-1.5 py-1 text-[11px] leading-tight " +
        (STATUS[b.status] ?? "bg-zinc-100 text-zinc-600 border-zinc-200")
      }
      title={`${b.event_type} · ${b.customer_name} · ${b.attendees} pax · ${inr(
        b.quoted_amount,
      )} (adv ${inr(b.advance_received)})`}
    >
      <div className="font-semibold">{b.event_type}</div>
      <div className="truncate">{b.customer_name}</div>
      <div className="text-[10px] opacity-80">
        {b.start_time || "-"}
        {b.attendees ? ` · ${b.attendees}p` : ""}
      </div>
    </div>
  )
}

export default function VenueCalendar() {
  const [start, setStart] = useState(today)
  const [data, setData] = useState<VenueCalendarData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    venueCalendar(DAYS, start)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [start])
  useEffect(load, [load])

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Venue calendar</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Banquet &amp; function diary - each venue's schedule.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" onClick={() => setStart(shift(start, -DAYS))}>
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" onClick={() => setStart(today)}>
            Today
          </Button>
          <Button variant="outline" onClick={() => setStart(shift(start, DAYS))}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        {data && data.venues.length === 0 && (
          <p className="py-8 text-center text-sm text-zinc-400">
            No venues yet - add them under Venues.
          </p>
        )}
        {data && data.venues.length > 0 && (
          <div className="overflow-x-auto">
            <table className="border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-white p-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                    Venue
                  </th>
                  {data.dates.map((d) => (
                    <th
                      key={d}
                      className={
                        "min-w-[92px] border-b border-zinc-200 p-1.5 text-center text-xs font-medium " +
                        (d === today ? "bg-brand-50 text-brand-700" : "text-zinc-500")
                      }
                    >
                      <div>{dow(d)}</div>
                      <div className="text-sm font-semibold">{dom(d)}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.venues.map((v) => (
                  <tr key={v.name}>
                    <td className="sticky left-0 z-10 border-b border-zinc-100 bg-white p-2 align-top">
                      <div className="font-medium">{v.venue_name}</div>
                      <div className="text-xs text-zinc-400">
                        {v.capacity ? `${v.capacity} pax · ` : ""}
                        {inr(v.base_price)}
                      </div>
                    </td>
                    {data.dates.map((d) => {
                      const cell = v.bookings.filter((b) => b.event_date === d)
                      return (
                        <td
                          key={d}
                          className={
                            "border-b border-l border-zinc-100 p-1 align-top " +
                            (d === today ? "bg-brand-50/40" : "")
                          }
                        >
                          {cell.map((b) => (
                            <Booking key={b.name} b={b} />
                          ))}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
          {Object.keys(STATUS).map((s) => (
            <span key={s} className="flex items-center gap-1.5">
              <span
                className={"inline-block size-3 rounded border " + STATUS[s]}
              />
              {s}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
