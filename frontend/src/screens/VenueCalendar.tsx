import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight, Plus, Search } from "lucide-react"

import {
  venueCalendar,
  getCurrentProperty,
  frappeFetch,
  type VenueBookingCell,
  type VenueCalendarData,
} from "../lib/api"
import {
  serverError,
  createResource,
  updateResource,
} from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cur, moneyLocale } from "../lib/money"

const DAYS = 14
const EVENT_TYPES = ["Wedding", "Conference", "Birthday", "Corporate Offsite", "Other"]
const STATUSES = ["Enquiry", "Confirmed", "Completed", "Cancelled"]
const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Draft = {
  name?: string
  venue: string
  event_type: string
  event_date: string
  start_time: string
  end_time: string
  customer_name: string
  customer_phone: string
  attendees: string
  quoted_amount: string
  status: string
  requirements: string
}

const emptyDraft = (venue: string, date: string): Draft => ({
  venue,
  event_type: "Wedding",
  event_date: date,
  start_time: "",
  end_time: "",
  customer_name: "",
  customer_phone: "",
  attendees: "",
  quoted_amount: "",
  status: "Enquiry",
  requirements: "",
})

const STATUS: Record<string, string> = {
  Enquiry: "bg-amber-100 text-amber-800 border-amber-200",
  Confirmed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  Completed: "bg-zinc-100 text-zinc-600 border-zinc-200",
  Cancelled: "bg-rose-100 text-rose-700 border-rose-200 line-through",
}

const inr = (n: number) =>
  `${cur()}` + Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

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
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    venueCalendar(DAYS, start)
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [start])
  useEffect(load, [load])

  const show = (b: VenueBookingCell) =>
    (!statusFilter || b.status === statusFilter) &&
    (!query ||
      b.customer_name?.toLowerCase().includes(query.toLowerCase()) ||
      b.name.toLowerCase().includes(query.toLowerCase()))

  async function openEdit(name: string) {
    try {
      const r = await frappeFetch<{ data: Record<string, unknown> }>(
        `/api/resource/Venue Booking/${encodeURIComponent(name)}`,
      )
      const d = r.data
      setDraft({
        name,
        venue: String(d.venue ?? ""),
        event_type: String(d.event_type ?? "Wedding"),
        event_date: String(d.event_date ?? ""),
        start_time: String(d.start_time ?? "").slice(0, 5),
        end_time: String(d.end_time ?? "").slice(0, 5),
        customer_name: String(d.customer_name ?? ""),
        customer_phone: String(d.customer_phone ?? ""),
        attendees: d.attendees ? String(d.attendees) : "",
        quoted_amount: d.quoted_amount ? String(d.quoted_amount) : "",
        status: String(d.status ?? "Enquiry"),
        requirements: String(d.requirements ?? ""),
      })
    } catch (e) {
      setError(serverError(e))
    }
  }

  async function saveDraft() {
    if (!draft) return
    if (!draft.customer_name.trim()) {
      setError("Customer name is required.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = {
        property: getCurrentProperty(),
        venue: draft.venue,
        event_type: draft.event_type,
        event_date: draft.event_date,
        start_time: draft.start_time || null,
        end_time: draft.end_time || null,
        customer_name: draft.customer_name,
        customer_phone: draft.customer_phone || null,
        attendees: draft.attendees ? Number(draft.attendees) : null,
        quoted_amount: draft.quoted_amount ? Number(draft.quoted_amount) : null,
        status: draft.status,
        requirements: draft.requirements || null,
      }
      if (draft.name) await updateResource("Venue Booking", draft.name, payload)
      else await createResource("Venue Booking", payload)
      setDraft(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const setField = (k: keyof Draft, v: string) =>
    setDraft((d) => (d ? { ...d, [k]: v } : d))

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Venue calendar</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Banquet &amp; function diary - each venue's schedule.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
            <input
              className={inputCls + " !w-44 pl-8"}
              placeholder="Search customer…"
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
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
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
                      const cell = v.bookings.filter(
                        (b) => b.event_date === d && show(b),
                      )
                      return (
                        <td
                          key={d}
                          onClick={(e) => {
                            // clicks that land on the empty part of the cell
                            // start a new booking for this venue + date
                            if (e.target === e.currentTarget)
                              setDraft(emptyDraft(v.name, d))
                          }}
                          className={
                            "group border-b border-l border-zinc-100 p-1 align-top " +
                            (d === today ? "bg-brand-50/40" : "") +
                            " cursor-pointer hover:bg-brand-50/60"
                          }
                        >
                          {cell.map((b) => (
                            <button
                              key={b.name}
                              onClick={() => openEdit(b.name)}
                              className="block w-full text-left"
                            >
                              <Booking b={b} />
                            </button>
                          ))}
                          {cell.length === 0 && (
                            <span className="flex items-center justify-center py-1 text-zinc-300 opacity-0 group-hover:opacity-100">
                              <Plus className="size-3.5" />
                            </span>
                          )}
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
          {Object.keys(STATUS).map((s) => (
            <span key={s} className="flex items-center gap-1.5">
              <span
                className={"inline-block size-3 rounded border " + STATUS[s]}
              />
              {s}
            </span>
          ))}
          <span className="text-zinc-400">
            · Click a day to add a booking, or a booking to edit it.
          </span>
        </div>
      </CardContent>

      {draft && (
        <Sheet
          title={draft.name ? "Edit venue booking" : "New venue booking"}
          onClose={() => setDraft(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button disabled={busy} onClick={saveDraft}>
                {draft.name ? "Save" : "Create booking"}
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <Field label="Venue">
              <select className={inputCls} value={draft.venue}
                onChange={(e) => setField("venue", e.target.value)}>
                {data?.venues.map((v) => (
                  <option key={v.name} value={v.name}>{v.venue_name}</option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Event type">
                <select className={inputCls} value={draft.event_type}
                  onChange={(e) => setField("event_type", e.target.value)}>
                  {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Date">
                <input type="date" className={inputCls} value={draft.event_date}
                  onChange={(e) => setField("event_date", e.target.value)} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start time">
                <input type="time" className={inputCls} value={draft.start_time}
                  onChange={(e) => setField("start_time", e.target.value)} />
              </Field>
              <Field label="End time">
                <input type="time" className={inputCls} value={draft.end_time}
                  onChange={(e) => setField("end_time", e.target.value)} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Customer name">
                <input className={inputCls} value={draft.customer_name}
                  onChange={(e) => setField("customer_name", e.target.value)} />
              </Field>
              <Field label="Customer phone">
                <input className={inputCls} value={draft.customer_phone}
                  onChange={(e) => setField("customer_phone", e.target.value)} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Attendees">
                <input type="number" className={inputCls} value={draft.attendees}
                  onChange={(e) => setField("attendees", e.target.value)} />
              </Field>
              <Field label="Quoted amount">
                <input type="number" className={inputCls} value={draft.quoted_amount}
                  onChange={(e) => setField("quoted_amount", e.target.value)} />
              </Field>
            </div>
            <Field label="Status">
              <select className={inputCls} value={draft.status}
                onChange={(e) => setField("status", e.target.value)}>
                {STATUSES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Requirements">
              <textarea rows={2} className={inputCls} value={draft.requirements}
                onChange={(e) => setField("requirements", e.target.value)} />
            </Field>
          </div>
        </Sheet>
      )}
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-zinc-600">{label}</span>
      {children}
    </label>
  )
}
