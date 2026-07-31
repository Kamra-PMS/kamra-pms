/*  The function diary - halls down the side, days across the top.

    What a banquet manager looks at when the phone rings and someone asks
    "do you have the 14th of December?". Confirmed functions own their
    cell; tentative holds are drawn softly, because they're meant to be
    pushed off by real business. Multi-day functions show on every day
    they run, numbered, so a three-day wedding reads as one thing. */

import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CalendarSearch, ChevronLeft, ChevronRight, Search } from "lucide-react"

import {
  banquet,
  type AvailabilityVenue,
  type BanquetCalendarCell,
  type BanquetCalendarData,
  type FunctionStatus,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import {
  dayName,
  Empty,
  ErrorNote,
  Field,
  inputCls,
  inr,
  shiftDate,
  STATUS_TONE,
  STATUSES,
  today,
} from "./banquet/shared"

const SPAN = 14

export default function BanquetDiary() {
  const navigate = useNavigate()
  const [start, setStart] = useState(today())
  const [data, setData] = useState<BanquetCalendarData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [check, setCheck] = useState(false)

  const load = useCallback(() => {
    banquet
      .calendar(start, SPAN)
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [start])
  useEffect(load, [load])

  const shows = (b: BanquetCalendarCell) =>
    (!statusFilter || b.status === statusFilter) &&
    (!query ||
      b.customer_name?.toLowerCase().includes(query.toLowerCase()) ||
      (b.company ?? "").toLowerCase().includes(query.toLowerCase()) ||
      b.name.toLowerCase().includes(query.toLowerCase()))

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Function diary</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Every hall's fortnight. Click a day to check availability, or a
            function to open it.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
            <input
              className={inputCls + " !w-44 pl-8"}
              placeholder="Customer…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <select
            className={inputCls + " !w-auto"}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <Button variant="outline" onClick={() => setCheck(true)}>
            <CalendarSearch className="size-4" />
            Check a date
          </Button>
          <Button
            variant="outline"
            onClick={() => setStart(shiftDate(start, -SPAN))}
            aria-label="Earlier"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" onClick={() => setStart(today())}>
            Today
          </Button>
          <Button
            variant="outline"
            onClick={() => setStart(shiftDate(start, SPAN))}
            aria-label="Later"
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ErrorNote error={error} />
        {data && data.venues.length === 0 && (
          <Empty>No halls yet - add them under Venues.</Empty>
        )}
        {data && data.venues.length > 0 && (
          <div className="overflow-x-auto">
            <table className="border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-white p-2 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                    Hall
                  </th>
                  {data.dates.map((d) => (
                    <th
                      key={d}
                      className={
                        "min-w-[104px] border-b border-zinc-200 p-1.5 text-center text-xs font-medium " +
                        (d === today()
                          ? "bg-brand-50 text-brand-700"
                          : "text-zinc-500")
                      }
                    >
                      <div>{dayName(d)}</div>
                      <div className="text-sm font-semibold">{d.slice(8)}</div>
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
                      const cells = (v.by_date?.[d] ?? []).filter(shows)
                      return (
                        <td
                          key={d}
                          className={
                            "group border-b border-l border-zinc-100 p-1 align-top " +
                            (d === today() ? "bg-brand-50/40" : "")
                          }
                        >
                          {cells.length === 0 && (
                            <button
                              onClick={() =>
                                navigate(
                                  `/banquet?venue=${encodeURIComponent(v.name)}` +
                                    `&date=${d}`,
                                )
                              }
                              aria-label="Open - start an enquiry"
                              className="flex w-full items-center justify-center rounded py-2 text-zinc-300 opacity-0 transition-opacity hover:bg-brand-50 hover:text-brand-600 group-hover:opacity-100"
                            >
                              +
                            </button>
                          )}
                          {cells.map((b) => (
                            <button
                              key={b.name + d}
                              onClick={() =>
                                navigate(`/banquet/${encodeURIComponent(b.name)}`)
                              }
                              className="block w-full text-left"
                            >
                              <FunctionChip b={b} />
                            </button>
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
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
          {(
            ["Enquiry", "Tentative", "Confirmed", "Completed"] as FunctionStatus[]
          ).map((s) => (
            <span key={s} className="flex items-center gap-1.5">
              <span
                className={
                  "inline-block size-3 rounded ring-1 ring-inset " +
                  STATUS_TONE[s]
                }
              />
              {s}
            </span>
          ))}
        </div>
      </CardContent>

      {check && <AvailabilitySheet onClose={() => setCheck(false)} />}
    </Card>
  )
}

function FunctionChip({ b }: { b: BanquetCalendarCell }) {
  return (
    <div
      className={
        "mb-1 rounded-md px-1.5 py-1 text-[11px] leading-tight ring-1 ring-inset " +
        (STATUS_TONE[b.status] ?? "bg-zinc-100 text-zinc-600 ring-zinc-500/20") +
        (b.status === "Tentative" ? " border-dashed" : "")
      }
      title={`${b.event_type} · ${b.customer_name} · ${b.pax} pax · ${inr(
        b.grand_total,
      )}${b.balance_due > 0 ? ` (${inr(b.balance_due)} due)` : ""}`}
    >
      <div className="truncate font-semibold">
        {b.event_name || b.event_type}
        {b.day_span > 1 && (
          <span className="font-normal opacity-70">
            {" "}
            {b.day_index}/{b.day_span}
          </span>
        )}
      </div>
      <div className="truncate">{b.customer_name}</div>
      <div className="truncate text-[10px] opacity-80">
        {b.start_time || "-"}
        {b.pax ? ` · ${b.pax}p` : ""}
      </div>
    </div>
  )
}

/* ── "do you have the 14th?" ──────────────────────────────────────────── */

function AvailabilitySheet({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({
    event_date: today(),
    end_date: "",
    start_time: "19:00",
    end_time: "23:00",
    pax: "",
  })
  const [venues, setVenues] = useState<AvailabilityVenue[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    banquet
      .availability({
        event_date: form.event_date,
        end_date: form.end_date || null,
        start_time: form.start_time || null,
        end_time: form.end_time || null,
        pax: Number(form.pax) || 0,
      })
      .then((r) => live && setVenues(r.venues))
      .catch((e) => live && setError(serverError(e)))
    return () => {
      live = false
    }
  }, [form])

  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }))

  return (
    <Sheet
      title="Is the hall free?"
      description="Two functions can share a hall morning and evening - only a real overlap in hours counts as taken."
      onClose={onClose}
      wide
    >
      <ErrorNote error={error} />
      <div className="grid gap-3 sm:grid-cols-5">
        <Field label="Date">
          <input
            type="date"
            className={inputCls}
            value={form.event_date}
            onChange={(e) => set("event_date", e.target.value)}
          />
        </Field>
        <Field label="Ends">
          <input
            type="date"
            className={inputCls}
            value={form.end_date}
            onChange={(e) => set("end_date", e.target.value)}
          />
        </Field>
        <Field label="From">
          <input
            type="time"
            className={inputCls}
            value={form.start_time}
            onChange={(e) => set("start_time", e.target.value)}
          />
        </Field>
        <Field label="To">
          <input
            type="time"
            className={inputCls}
            value={form.end_time}
            onChange={(e) => set("end_time", e.target.value)}
          />
        </Field>
        <Field label="Pax">
          <input
            type="number"
            className={inputCls}
            value={form.pax}
            onChange={(e) => set("pax", e.target.value)}
          />
        </Field>
      </div>

      <div className="mt-4 space-y-2">
        {venues === null ? (
          <Empty>Checking…</Empty>
        ) : (
          venues.map((v) => (
            <div
              key={v.name}
              className={
                "rounded-lg border px-3 py-2 " +
                (v.available
                  ? v.fits
                    ? "border-emerald-200 bg-emerald-50/50"
                    : "border-amber-200 bg-amber-50/50"
                  : "border-rose-200 bg-rose-50/50")
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">
                    {v.venue_name}
                    <span className="ml-2 text-xs font-normal text-zinc-500">
                      {v.venue_type} · seats {v.capacity}
                      {v.min_capacity ? ` (min ${v.min_capacity})` : ""}
                      {v.area_sqft ? ` · ${v.area_sqft} sq ft` : ""}
                    </span>
                  </p>
                  {v.setup_styles && (
                    <p className="text-xs text-zinc-400">{v.setup_styles}</p>
                  )}
                  {!v.available && (
                    <p className="mt-1 text-xs text-rose-700">
                      {v.conflicts
                        .filter((c) => c.kind === "confirmed")
                        .map(
                          (c) =>
                            `${c.customer_name} on ${c.event_date}` +
                            (c.start_time
                              ? ` ${String(c.start_time).slice(0, 5)}–${String(
                                  c.end_time ?? "",
                                ).slice(0, 5)}`
                              : ""),
                        )
                        .join("; ")}
                    </p>
                  )}
                  {v.available &&
                    v.conflicts.some((c) => c.kind === "tentative") && (
                      <p className="mt-1 text-xs text-amber-700">
                        Soft hold you can sell over:{" "}
                        {v.conflicts
                          .filter((c) => c.kind === "tentative")
                          .map((c) => c.customer_name)
                          .join(", ")}
                      </p>
                    )}
                  {v.available && !v.fits && (
                    <p className="mt-1 text-xs text-amber-700">
                      Smaller than the pax count.
                    </p>
                  )}
                  {v.available && v.under_minimum && (
                    <p className="mt-1 text-xs text-amber-700">
                      Below this hall's usual minimum - check the minimum spend.
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right text-sm">
                  <p className="tabular-nums">{inr(v.base_price)}</p>
                  {v.hourly_rate > 0 && (
                    <p className="text-xs text-zinc-400">
                      {inr(v.hourly_rate)}/hr
                      {v.min_hours ? `, min ${v.min_hours}h` : ""}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </Sheet>
  )
}
