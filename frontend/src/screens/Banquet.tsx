/*  Banquets - the sales desk.

    Three things a banquet manager does before lunch: chase what's gone
    quiet, look at where the month is landing, and open a new enquiry. So
    this screen is the reminder list, the month-by-month board and the
    pipeline, with the enquiry form one click away. Each function opens on
    its own sheet at /banquet/:name. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  AlertTriangle,
  CalendarDays,
  PartyPopper,
  Plus,
  Search,
  TrendingUp,
} from "lucide-react"

import {
  banquet,
  type AvailabilityVenue,
  type BanquetPipeline,
  type FunctionStatus,
  type ReminderRow,
} from "../lib/api"
import { listResource, serverError, type Row } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import {
  Empty,
  ErrorNote,
  EVENT_TYPES,
  Field,
  inputCls,
  inr,
  monthName,
  Select,
  SOURCES,
  Stat,
  StatusPill,
  STATUSES,
  today,
} from "./banquet/shared"

type Tab = "today" | "pipeline" | "functions"

interface FunctionRow extends Row {
  customer_name: string
  venue: string
  event_type: string
  status: FunctionStatus
  event_date: string
  end_date: string | null
  attendees: number
  pax_guaranteed: number
  grand_total: number
  balance_due: number
  follow_up_date: string | null
  company: string | null
  sales_owner: string | null
}

export default function Banquet() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>("today")
  const [error, setError] = useState<string | null>(null)
  const [reminders, setReminders] = useState<ReminderRow[] | null>(null)
  const [pipeline, setPipeline] = useState<BanquetPipeline | null>(null)
  const [rows, setRows] = useState<FunctionRow[] | null>(null)
  const [query, setQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [enquiry, setEnquiry] = useState(false)

  const load = useCallback(() => {
    banquet
      .reminders(60)
      .then((r) => setReminders(r.functions))
      .catch((e) => setError(serverError(e)))
    banquet
      .pipeline({ months: 6 })
      .then(setPipeline)
      .catch((e) => setError(serverError(e)))
    listResource("Venue Booking", {
      fields: [
        "name",
        "customer_name",
        "venue",
        "event_type",
        "status",
        "event_date",
        "end_date",
        "attendees",
        "pax_guaranteed",
        "grand_total",
        "balance_due",
        "follow_up_date",
        "company",
        "sales_owner",
      ],
      orderBy: "event_date asc",
      limit: 300,
    })
      .then((r) => setRows(r as unknown as FunctionRow[]))
      .catch((e) => setError(serverError(e)))
  }, [])
  useEffect(load, [load])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (rows ?? []).filter(
      (r) =>
        (!statusFilter || r.status === statusFilter) &&
        (!q ||
          r.customer_name?.toLowerCase().includes(q) ||
          r.name.toLowerCase().includes(q) ||
          r.venue?.toLowerCase().includes(q) ||
          (r.company ?? "").toLowerCase().includes(q)),
    )
  }, [rows, query, statusFilter])

  const urgent = (reminders ?? []).filter((f) =>
    f.alerts.some((a) => a.urgency === "high"),
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <PartyPopper className="size-5 text-violet-600" />
            Banquets
          </h1>
          <p className="mt-0.5 text-sm text-zinc-400">
            Function prospecting through to the event order - enquiry,
            quotation, contract, and the day itself.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate("/banquet-diary")}>
            <CalendarDays className="size-4" />
            Diary
          </Button>
          <Button onClick={() => setEnquiry(true)}>
            <Plus className="size-4" />
            New enquiry
          </Button>
        </div>
      </div>

      <ErrorNote error={error} />

      {pipeline && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Confirmed, 6 months"
            value={inr(pipeline.totals.confirmed_value)}
            sub={`${pipeline.totals.functions} functions on the books`}
          />
          <Stat
            label="Still in play"
            value={inr(pipeline.totals.pipeline_value)}
            sub="Enquiries and tentative holds"
            tone="text-amber-700"
          />
          <Stat
            label="Outstanding"
            value={inr(pipeline.totals.outstanding)}
            sub="Confirmed but unpaid"
            tone={pipeline.totals.outstanding ? "text-rose-700" : ""}
          />
          <Stat
            label="Conversion"
            value={
              pipeline.totals.conversion_rate === null
                ? "-"
                : `${pipeline.totals.conversion_rate}%`
            }
            sub="Of everything decided"
          />
        </div>
      )}

      <div className="flex gap-1 border-b border-zinc-200">
        {(
          [
            ["today", `Needs chasing${urgent.length ? ` (${urgent.length})` : ""}`],
            ["pipeline", "Month by month"],
            ["functions", "All functions"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors " +
              (tab === id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-zinc-500 hover:text-zinc-800")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "today" && (
        <RemindersBoard
          rows={reminders}
          onOpen={(fn) => navigate(`/banquet/${encodeURIComponent(fn)}`)}
        />
      )}

      {tab === "pipeline" && <PipelineBoard data={pipeline} />}

      {tab === "functions" && (
        <Card>
          <CardHeader>
            <CardTitle>All functions</CardTitle>
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
                <input
                  className={inputCls + " !w-52 pl-8"}
                  placeholder="Customer, company, hall…"
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
            </div>
          </CardHeader>
          <CardContent>
            {visible.length === 0 ? (
              <Empty>
                {rows === null
                  ? "Loading…"
                  : "Nothing here yet - start with a new enquiry."}
              </Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
                      <th className="py-2 pr-3 font-medium">Date</th>
                      <th className="py-2 pr-3 font-medium">Customer</th>
                      <th className="py-2 pr-3 font-medium">Hall</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 text-right font-medium">Pax</th>
                      <th className="py-2 pr-3 text-right font-medium">Value</th>
                      <th className="py-2 pr-3 text-right font-medium">Due</th>
                      <th className="py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((r) => (
                      <tr
                        key={r.name}
                        onClick={() =>
                          navigate(`/banquet/${encodeURIComponent(r.name)}`)
                        }
                        className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50"
                      >
                        <td className="py-2 pr-3 whitespace-nowrap tabular-nums">
                          {r.event_date}
                          {r.end_date && r.end_date !== r.event_date && (
                            <span className="text-zinc-400"> → {r.end_date}</span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-medium">{r.customer_name}</div>
                          {r.company && (
                            <div className="text-xs text-zinc-400">
                              {r.company}
                            </div>
                          )}
                        </td>
                        <td className="py-2 pr-3 text-zinc-600">{r.venue}</td>
                        <td className="py-2 pr-3 text-zinc-600">
                          {r.event_type}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {r.pax_guaranteed || r.attendees || "-"}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {inr(r.grand_total)}
                        </td>
                        <td
                          className={
                            "py-2 pr-3 text-right tabular-nums " +
                            (r.balance_due > 0 ? "text-rose-700" : "text-zinc-400")
                          }
                        >
                          {inr(r.balance_due)}
                        </td>
                        <td className="py-2">
                          <StatusPill status={r.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {enquiry && (
        <EnquirySheet
          onClose={() => setEnquiry(false)}
          onCreated={(fn) => {
            setEnquiry(false)
            navigate(`/banquet/${encodeURIComponent(fn)}`)
          }}
        />
      )}
    </div>
  )
}

/* ── what needs chasing ───────────────────────────────────────────────── */

function RemindersBoard({
  rows,
  onOpen,
}: {
  rows: ReminderRow[] | null
  onOpen: (fn: string) => void
}) {
  if (rows === null) return <Empty>Loading…</Empty>
  if (rows.length === 0)
    return (
      <Card>
        <CardContent>
          <Empty>
            Nothing is waiting on you - every follow-up, hold and payment is
            current.
          </Empty>
        </CardContent>
      </Card>
    )
  return (
    <div className="space-y-2">
      {rows.map((f) => {
        const high = f.alerts.some((a) => a.urgency === "high")
        return (
          <button
            key={f.function}
            onClick={() => onOpen(f.function)}
            className={
              "flex w-full items-start gap-3 rounded-xl border bg-white px-4 py-3 text-left " +
              "transition-colors hover:bg-zinc-50 " +
              (high ? "border-amber-300" : "border-zinc-200")
            }
          >
            <AlertTriangle
              className={
                "mt-0.5 size-4 shrink-0 " +
                (high ? "text-amber-600" : "text-zinc-300")
              }
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{f.customer_name}</span>
                <StatusPill status={f.status} />
                <span className="text-xs text-zinc-400">
                  {f.venue} · {f.event_date}
                </span>
              </div>
              <ul className="mt-1 space-y-0.5">
                {f.alerts.map((a, i) => (
                  <li
                    key={i}
                    className={
                      "text-sm " +
                      (a.urgency === "high" ? "text-amber-800" : "text-zinc-500")
                    }
                  >
                    {a.message}
                  </li>
                ))}
              </ul>
            </div>
            <div className="shrink-0 text-right text-sm tabular-nums">
              <div>{inr(f.grand_total)}</div>
              {f.balance_due > 0 && (
                <div className="text-xs text-rose-700">
                  {inr(f.balance_due)} due
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

/* ── month by month ───────────────────────────────────────────────────── */

function PipelineBoard({ data }: { data: BanquetPipeline | null }) {
  if (!data) return <Empty>Loading…</Empty>
  const peak = Math.max(
    1,
    ...data.months.map((m) => m.confirmed_value + m.pipeline_value),
  )
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="inline-flex items-center gap-1.5">
              <TrendingUp className="size-4" />
              Where the months are landing
            </span>
          </CardTitle>
          <span className="text-xs text-zinc-400">
            {data.from} → {data.to}, by event date
          </span>
        </CardHeader>
        <CardContent>
          {data.months.length === 0 ? (
            <Empty>No functions in this window.</Empty>
          ) : (
            <div className="space-y-3">
              {data.months.map((m) => (
                <div key={m.month}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium">{monthName(m.month)}</span>
                    <span className="tabular-nums text-zinc-500">
                      {inr(m.confirmed_value)} confirmed
                      {m.pipeline_value > 0 && (
                        <span className="text-amber-700">
                          {" "}
                          + {inr(m.pipeline_value)} in play
                        </span>
                      )}
                      <span className="text-zinc-400">
                        {" "}
                        · {m.count} function{m.count === 1 ? "" : "s"} ·{" "}
                        {m.pax} pax
                      </span>
                    </span>
                  </div>
                  <div className="mt-1 flex h-2.5 overflow-hidden rounded-full bg-zinc-100">
                    <div
                      className="bg-emerald-500"
                      style={{
                        width: `${(m.confirmed_value / peak) * 100}%`,
                      }}
                    />
                    <div
                      className="bg-amber-400"
                      style={{ width: `${(m.pipeline_value / peak) * 100}%` }}
                    />
                  </div>
                  {m.outstanding > 0 && (
                    <p className="mt-0.5 text-xs text-rose-700">
                      {inr(m.outstanding)} still to collect
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <BreakdownCard title="By status" rows={data.by_status} />
        <BreakdownCard title="By event type" rows={data.by_event_type} />
        <BreakdownCard title="By hall" rows={data.by_venue} />
      </div>

      {data.lost_reasons.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Why business went away</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {data.lost_reasons.map((r) => (
                <li key={r.reason} className="flex justify-between gap-3">
                  <span className="text-zinc-600">{r.reason}</span>
                  <span className="tabular-nums text-zinc-400">{r.count}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function BreakdownCard({
  title,
  rows,
}: {
  title: string
  rows: BanquetPipeline["by_status"]
}) {
  const peak = Math.max(1, ...rows.map((r) => r.value))
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <Empty>Nothing yet.</Empty>
        ) : (
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.key}>
                <div className="flex justify-between text-sm">
                  <span className="truncate text-zinc-600">{r.key}</span>
                  <span className="shrink-0 tabular-nums">
                    {inr(r.value)}{" "}
                    <span className="text-zinc-400">({r.count})</span>
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-100">
                  <div
                    className="h-full bg-brand-500"
                    style={{ width: `${(r.value / peak) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

/* ── the new enquiry ──────────────────────────────────────────────────── */

function EnquirySheet({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (fn: string) => void
}) {
  const [form, setForm] = useState({
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    company: "",
    event_type: "Wedding",
    event_date: today(),
    end_date: "",
    start_time: "19:00",
    end_time: "23:00",
    attendees: "",
    venue: "",
    source: "Phone",
    requirements: "",
  })
  const [avail, setAvail] = useState<AvailabilityVenue[] | null>(null)
  const [companies, setCompanies] = useState<Row[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => {
    listResource("Company", { fields: ["name", "company_name"], limit: 200 })
      .then(setCompanies)
      .catch(() => {})
  }, [])

  // the halls free for these dates re-check themselves as the date, hours
  // and pax move - picking a booked hall shouldn't be possible by accident
  useEffect(() => {
    if (!form.event_date) return
    let live = true
    banquet
      .availability({
        event_date: form.event_date,
        end_date: form.end_date || null,
        start_time: form.start_time || null,
        end_time: form.end_time || null,
        pax: Number(form.attendees) || 0,
      })
      .then((r) => {
        if (!live) return
        setAvail(r.venues)
        setForm((f) =>
          f.venue && r.venues.some((v) => v.name === f.venue)
            ? f
            : { ...f, venue: r.venues.find((v) => v.available && v.fits)?.name ?? "" },
        )
      })
      .catch((e) => live && setError(serverError(e)))
    return () => {
      live = false
    }
  }, [form.event_date, form.end_date, form.start_time, form.end_time, form.attendees])

  async function submit() {
    if (!form.customer_name.trim()) return setError("Whose function is this?")
    if (!form.venue) return setError("Pick a hall.")
    setBusy(true)
    setError(null)
    try {
      const r = await banquet.createEnquiry({
        venue: form.venue,
        event_date: form.event_date,
        end_date: form.end_date || null,
        start_time: form.start_time || null,
        end_time: form.end_time || null,
        customer_name: form.customer_name,
        customer_phone: form.customer_phone || null,
        customer_email: form.customer_email || null,
        company: form.company || null,
        event_type: form.event_type,
        attendees: Number(form.attendees) || 0,
        source: form.source,
        requirements: form.requirements || null,
      })
      onCreated(r.function)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const chosen = avail?.find((v) => v.name === form.venue)

  return (
    <Sheet
      title="New function enquiry"
      description="The hall's rack rental goes on as the first line - the number the conversation starts from."
      onClose={onClose}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy} onClick={submit}>
            Open the enquiry
          </Button>
        </div>
      }
    >
      <ErrorNote error={error} />
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Customer name">
            <input
              className={inputCls}
              value={form.customer_name}
              onChange={(e) => set("customer_name", e.target.value)}
            />
          </Field>
          <Field label="Phone">
            <input
              className={inputCls}
              value={form.customer_phone}
              onChange={(e) => set("customer_phone", e.target.value)}
            />
          </Field>
          <Field label="Email">
            <input
              className={inputCls}
              value={form.customer_email}
              onChange={(e) => set("customer_email", e.target.value)}
            />
          </Field>
          <Field
            label="Company"
            hint="Set for corporate business - it also decides which folio the bill lands on."
          >
            <select
              className={inputCls}
              value={form.company}
              onChange={(e) => set("company", e.target.value)}
            >
              <option value="">Not a corporate booking</option>
              {companies.map((c) => (
                <option key={c.name} value={c.name}>
                  {String(c.company_name ?? c.name)}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Event type">
            <Select
              value={form.event_type}
              onChange={(v) => set("event_type", v)}
              options={EVENT_TYPES}
            />
          </Field>
          <Field label="Date">
            <input
              type="date"
              className={inputCls}
              value={form.event_date}
              onChange={(e) => set("event_date", e.target.value)}
            />
          </Field>
          <Field label="Ends" hint="Blank for a single day">
            <input
              type="date"
              className={inputCls}
              value={form.end_date}
              onChange={(e) => set("end_date", e.target.value)}
            />
          </Field>
          <Field label="Expected pax">
            <input
              type="number"
              className={inputCls}
              value={form.attendees}
              onChange={(e) => set("attendees", e.target.value)}
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
          <Field label="Came from">
            <Select
              value={form.source}
              onChange={(v) => set("source", v)}
              options={SOURCES}
            />
          </Field>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-zinc-500">
            Which hall - free for these dates and hours
          </p>
          {avail === null ? (
            <p className="text-sm text-zinc-400">Checking…</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {avail.map((v) => {
                const blocked = !v.available
                const tooSmall = !v.fits
                return (
                  <button
                    key={v.name}
                    disabled={blocked}
                    onClick={() => set("venue", v.name)}
                    className={
                      "rounded-lg border px-3 py-2 text-left text-sm transition-colors " +
                      (form.venue === v.name
                        ? "border-brand-600 bg-brand-50"
                        : blocked
                          ? "border-zinc-200 bg-zinc-50 opacity-60"
                          : "border-zinc-200 hover:bg-zinc-50")
                    }
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{v.venue_name}</span>
                      <span className="tabular-nums text-zinc-500">
                        {inr(v.base_price)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-zinc-400">
                      {v.venue_type} · seats {v.capacity}
                      {v.hourly_rate ? ` · ${inr(v.hourly_rate)}/hr` : ""}
                    </div>
                    {blocked && (
                      <div className="mt-1 text-xs text-rose-700">
                        Taken: {v.conflicts[0]?.customer_name}
                      </div>
                    )}
                    {!blocked && tooSmall && (
                      <div className="mt-1 text-xs text-amber-700">
                        Smaller than the pax count
                      </div>
                    )}
                    {!blocked &&
                      v.conflicts.some((c) => c.kind === "tentative") && (
                        <div className="mt-1 text-xs text-amber-700">
                          Soft hold you can sell over
                        </div>
                      )}
                  </button>
                )
              })}
            </div>
          )}
          {chosen && chosen.under_minimum && (
            <p className="mt-2 text-xs text-amber-700">
              {chosen.venue_name} usually takes {chosen.min_capacity}+ - check
              the minimum spend applies.
            </p>
          )}
        </div>

        <Field label="What they asked for">
          <textarea
            rows={3}
            className={inputCls}
            placeholder="300 pax sangeet, veg buffet, DJ till 1am, green room for the bride…"
            value={form.requirements}
            onChange={(e) => set("requirements", e.target.value)}
          />
        </Field>
      </div>
    </Sheet>
  )
}
