/*  The month, at a glance.

    A banquet office gets asked one question more than any other: "do you
    have the 14th of December?" Not "what are your hours" — a hall is sold
    by the session, and the answer is yes or no for a specific hall on a
    specific evening.

    So this is that answer, for a whole month at once: halls down the side
    split into morning / afternoon / evening, days across the top, every
    cell either open or carrying its function. Colour does the reading for
    you — the eye finds the free Saturday evening before you've finished
    the sentence. Click an open cell to start the enquiry already knowing
    the hall, the date and the session. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CalendarRange, ChevronLeft, ChevronRight, Sparkles } from "lucide-react"

import {
  banquet,
  type FunctionStatus,
  type MonthAvailability,
  type MonthCell,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Empty, ErrorNote, inr, StatusPill, today } from "./banquet/shared"

const SESSIONS = ["Morning", "Afternoon", "Evening"] as const

/** How a taken cell reads at a glance. Confirmed is solid; a tentative
 *  hold is drawn softly, because it's meant to be sellable over. */
const CELL: Record<string, string> = {
  Confirmed: "bg-emerald-500 text-white",
  Completed: "bg-zinc-400 text-white",
  Tentative:
    "bg-amber-100 text-amber-900 ring-1 ring-inset ring-dashed ring-amber-400",
  Enquiry: "bg-sky-100 text-sky-800 ring-1 ring-inset ring-sky-300",
}

function monthShift(month: string, by: number) {
  const [y, m] = month.split("-").map(Number)
  const d = new Date(y, m - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}
const monthLabel = (m: string) =>
  new Date(m + "-01T00:00:00").toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  })
const weekend = (iso: string) => [0, 6].includes(new Date(iso + "T00:00:00").getDay())

export default function BanquetMonth() {
  const navigate = useNavigate()
  const [month, setMonth] = useState(today().slice(0, 7))
  const [data, setData] = useState<MonthAvailability | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)

  const load = useCallback(() => {
    setData(null)
    banquet
      .monthAvailability(month)
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [month])
  useEffect(load, [load])

  /** The headline a salesperson actually wants: how much of the month is
   *  still sellable, and which prime slots are still open. */
  const openPrime = useMemo(() => {
    if (!data) return []
    return data.dates
      .filter(weekend)
      .flatMap((d) =>
        data.rows
          .filter((r) => r.session === "Evening" && !(r.by_date[d]?.length))
          .map((r) => ({ date: d, venue: r.venue_name, row: r })),
      )
  }, [data])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <CalendarRange className="size-4" />
                {monthLabel(month)}
              </span>
            </CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              Every hall, every session. Click an open slot to start an
              enquiry on it.
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              onClick={() => setMonth(monthShift(month, -1))}
              aria-label="Previous month"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" onClick={() => setMonth(today().slice(0, 7))}>
              This month
            </Button>
            <Button
              variant="outline"
              onClick={() => setMonth(monthShift(month, 1))}
              aria-label="Next month"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <ErrorNote error={error} />
          {!data ? (
            <Empty>Loading the month…</Empty>
          ) : data.rows.length === 0 ? (
            <Empty>No halls yet — add them under Halls &amp; Venues.</Empty>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-4">
                <Gauge value={data.utilisation} />
                {openPrime.length > 0 && (
                  <p className="flex items-center gap-1.5 text-sm text-zinc-500">
                    <Sparkles className="size-4 text-amber-500" />
                    <span>
                      <span className="font-medium text-zinc-800">
                        {openPrime.length} weekend evening
                        {openPrime.length === 1 ? "" : "s"}
                      </span>{" "}
                      still open — the slots worth selling first.
                    </span>
                  </p>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="border-separate border-spacing-0 text-sm">
                  <thead>
                    <tr>
                      <th className="sticky left-0 z-20 bg-white p-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        Hall
                      </th>
                      <th className="sticky left-[9.5rem] z-20 bg-white p-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        Session
                      </th>
                      {data.dates.map((d) => (
                        <th
                          key={d}
                          className={
                            "min-w-8 border-b border-zinc-200 px-0.5 pb-1.5 text-center text-[11px] font-medium " +
                            (d === today()
                              ? "bg-brand-50 text-brand-700"
                              : weekend(d)
                                ? "text-zinc-700"
                                : "text-zinc-400")
                          }
                        >
                          <div className="text-[9px] uppercase">
                            {new Date(d + "T00:00:00")
                              .toLocaleDateString("en-US", { weekday: "narrow" })}
                          </div>
                          {Number(d.slice(8))}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((r, i) => {
                      const firstOfVenue =
                        i === 0 || data.rows[i - 1].venue !== r.venue
                      return (
                        <tr key={r.venue + r.session}>
                          {firstOfVenue ? (
                            <td
                              rowSpan={SESSIONS.length}
                              className="sticky left-0 z-10 w-38 border-b border-zinc-100 bg-white p-2 align-top"
                            >
                              <div className="font-medium">{r.venue_name}</div>
                              <div className="text-xs text-zinc-400">
                                {r.capacity ? `${r.capacity} pax · ` : ""}
                                {inr(r.base_price)}
                              </div>
                            </td>
                          ) : null}
                          <td
                            className={
                              "sticky left-[9.5rem] z-10 whitespace-nowrap bg-white px-2 py-1 text-xs text-zinc-500 " +
                              (r.session === "Evening"
                                ? "border-b border-zinc-100"
                                : "")
                            }
                          >
                            {r.session}
                          </td>
                          {data.dates.map((d) => {
                            const cells = r.by_date[d] ?? []
                            const b = cells[0]
                            const key = `${r.venue}|${r.session}|${d}`
                            return (
                              <td
                                key={d}
                                className={
                                  "px-0.5 py-0.5 " +
                                  (r.session === "Evening"
                                    ? "border-b border-zinc-100"
                                    : "") +
                                  (d === today() ? " bg-brand-50/40" : "")
                                }
                                onMouseEnter={() => setHover(key)}
                                onMouseLeave={() => setHover(null)}
                              >
                                <Slot
                                  cell={b}
                                  extra={cells.length - 1}
                                  showing={hover === key}
                                  weekend={weekend(d)}
                                  onOpen={() =>
                                    b
                                      ? navigate(
                                          `/banquet/${encodeURIComponent(b.name)}`,
                                        )
                                      : navigate(
                                          `/banquet?venue=${encodeURIComponent(
                                            r.venue,
                                          )}&date=${d}&session=${r.session}`,
                                        )
                                  }
                                />
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                {(Object.keys(CELL) as FunctionStatus[]).map((s) => (
                  <span key={s} className="flex items-center gap-1.5">
                    <span className={"inline-block size-3 rounded " + CELL[s]} />
                    {s}
                  </span>
                ))}
                <span className="flex items-center gap-1.5">
                  <span className="inline-block size-3 rounded border border-dashed border-zinc-300" />
                  Open
                </span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/** One hall-session-day. Free slots stay quiet until you hover them; taken
 *  ones carry their colour and reveal the booking on hover. */
function Slot({
  cell,
  extra,
  showing,
  weekend: isWeekend,
  onOpen,
}: {
  cell: MonthCell | undefined
  extra: number
  showing: boolean
  weekend: boolean
  onOpen: () => void
}) {
  return (
    <div className="relative">
      <button
        onClick={onOpen}
        aria-label={
          cell
            ? `${cell.customer_name}, ${cell.event_type}`
            : "Open — start an enquiry"
        }
        className={
          "block h-7 w-full rounded transition-all " +
          (cell
            ? (CELL[cell.status] ?? "bg-zinc-300") + " hover:brightness-110"
            : "border border-dashed " +
              (isWeekend
                ? "border-zinc-300 hover:border-brand-500 hover:bg-brand-50"
                : "border-zinc-200 hover:border-brand-400 hover:bg-brand-50/60"))
        }
      >
        {extra > 0 && (
          <span className="text-[9px] font-semibold">+{extra + 1}</span>
        )}
      </button>
      {showing && cell && (
        <div className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 w-52 -translate-x-1/2 rounded-lg bg-zinc-900 px-2.5 py-2 text-left text-xs text-white shadow-lg">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold">{cell.customer_name}</span>
            <StatusPill status={cell.status} className="!bg-white/15 !text-white !ring-0" />
          </div>
          <div className="mt-0.5 text-white/70">
            {cell.event_name || cell.event_type}
            {cell.pax ? ` · ${cell.pax} pax` : ""}
          </div>
          <div className="mt-1 text-white/90">
            {inr(cell.grand_total)}
            {cell.balance_due > 0 && (
              <span className="text-amber-300"> · {inr(cell.balance_due)} due</span>
            )}
          </div>
          {cell.spans_day && (
            <div className="mt-0.5 text-[10px] text-white/50">
              Part of a multi-day function
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** How much of the month is sold — one number a manager reads instantly. */
function Gauge({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-2 w-40 overflow-hidden rounded-full bg-zinc-100">
        <div
          className={
            "h-full rounded-full transition-all " +
            (value > 70
              ? "bg-emerald-500"
              : value > 35
                ? "bg-amber-400"
                : "bg-zinc-300")
          }
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className="text-sm">
        <span className="font-semibold tabular-nums">{value}%</span>
        <span className="text-zinc-400"> of hall-sessions sold</span>
      </span>
    </div>
  )
}
