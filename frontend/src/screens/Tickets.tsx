import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useRealtime } from "../lib/realtime"
import { AlertTriangle, Plus } from "lucide-react"
import { Sheet } from "../components/ui/sheet"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { cn } from "../lib/utils"
import { useT } from "../lib/i18n"

type View = "open" | "mine" | "unassigned" | "overdue" | "resolved" | "all"

interface Counts {
  open: number
  mine: number
  unassigned: number
  overdue: number
  resolved: number
  all: number
}

interface TicketEvent {
  kind: string
  by: string | null
  by_name: string | null
  at: string
  from_value: string | null
  to_value: string | null
  from_name?: string | null
  to_name?: string | null
  note: string | null
}

interface TicketDetail extends Ticket {
  description: string | null
  resolution_note: string | null
  assigned_by_name: string | null
  assigned_at: string | null
  first_response_at: string | null
  response_minutes: number | null
  resolve_minutes: number | null
  resolved_on: string | null
  events: TicketEvent[]
}

interface Staff {
  user: string
  name: string
}

const VIEWS: { id: View; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "mine", label: "Mine" },
  { id: "unassigned", label: "Unassigned" },
  { id: "overdue", label: "Overdue" },
  { id: "resolved", label: "Resolved" },
  { id: "all", label: "All" },
]

function human(mins: number | null | undefined): string {
  if (mins == null) return "-"
  const a = Math.abs(mins)
  if (a < 60) return `${a} min`
  if (a < 1440) return `${(a / 60).toFixed(1)} h`
  return `${(a / 1440).toFixed(1)} d`
}

interface Ticket {
  name: string
  subject: string
  category: string
  priority: string
  status: string
  source: string
  room: string | null
  guest_name: string | null
  due_by: string
  breached: 0 | 1
  overdue: boolean
  creation: string
  assigned_to_user: string | null
  assigned_to_name: string | null
  resolved_by: string | null
  resolved_by_name: string | null
  age_hours: number
  minutes_left: number | null
  reopened_count?: number
}

const CATEGORIES = [
  "Housekeeping", "Room Service", "Maintenance", "Front Desk",
  "Concierge", "Complaint", "Other",
]

const prioTone: Record<string, "zinc" | "sky" | "amber" | "rose"> = {
  Low: "zinc",
  Medium: "sky",
  High: "amber",
  Urgent: "rose",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

/** One ticket in full: SLA, who has it, who solved it, the timeline. */
function TicketSheet({
  name,
  staff,
  onClose,
  onChanged,
}: {
  name: string
  staff: Staff[]
  onClose: () => void
  onChanged: () => void
}) {
  const { t } = useT()
  const [d, setD] = useState<TicketDetail | null>(null)
  const [note, setNote] = useState("")
  const [resolution, setResolution] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(() => {
    call<TicketDetail>("kamra.tickets.ticket_detail", { ticket: name })
      .then(setD)
      .catch((e) => setErr(serverError(e)))
  }, [name])
  useEffect(load, [load])

  async function act(method: string, args: Record<string, unknown>, after?: () => void) {
    setBusy(true)
    setErr(null)
    try {
      setD(await call<TicketDetail>(`kamra.tickets.${method}`, { ticket: name, ...args }))
      after?.()
      onChanged()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const isOpen = d?.status === "Open" || d?.status === "In Progress"
  const eventText = (e: TicketEvent) => {
    const who = e.by_name || e.by || t("Someone")
    switch (e.kind) {
      case "Created":
        return t("{who} raised it ({source})", { who, source: e.to_value || t("Manual") })
      case "Assigned":
        return e.to_value
          ? t("{who} assigned it to {to}", { who, to: e.to_name || e.to_value })
          : t("{who} took the assignee off", { who })
      case "Status":
        return t("{who} moved it from {a} to {b}", { who, a: t(e.from_value || "-"), b: t(e.to_value || "-") })
      case "Reopened":
        return t("{who} reopened it", { who })
      case "Priority":
        return t("{who} changed priority {a} to {b}", { who, a: t(e.from_value || "-"), b: t(e.to_value || "-") })
      default:
        return t("{who} added a note", { who })
    }
  }

  return (
    <Sheet
      wide
      title={d ? d.subject : name}
      description={d ? `${d.name} · ${t(d.category)}` : undefined}
      onClose={onClose}
    >
      {err && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>
      )}
      {!d ? (
        <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={prioTone[d.priority] ?? "zinc"}>{t(d.priority)}</Badge>
            <Badge tone={isOpen ? "amber" : "green"}>{t(d.status)}</Badge>
            {d.source !== "Manual" && <Badge tone="brand">{t(d.source)}</Badge>}
            {d.reopened_count ? <Badge tone="rose">{t("Reopened {n}x", { n: d.reopened_count })}</Badge> : null}
            {d.room && <span className="text-xs text-zinc-500">{t("Room {n}", { n: d.room.split("-").pop() ?? "" })}</span>}
            {d.guest_name && <span className="text-xs text-zinc-500">{d.guest_name}</span>}
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {[
              [t("Age"), human(Math.round(d.age_hours * 60))],
              [
                isOpen ? (d.overdue ? t("Overdue by") : t("Time left")) : t("Solved in"),
                isOpen ? human(d.minutes_left) : human(d.resolve_minutes),
              ],
              [t("First response"), d.response_minutes == null ? t("None yet") : human(d.response_minutes)],
              [t("SLA"), d.breached || d.overdue ? t("Breached") : t("Within")],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-zinc-200 px-3 py-2">
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">{k}</p>
                <p className={cn("mt-0.5 font-semibold tabular-nums", !!(d.overdue || d.breached) && k === t("SLA") && "text-rose-600")}>{v}</p>
              </div>
            ))}
          </div>

          {d.description && <p className="whitespace-pre-wrap text-sm text-zinc-700">{d.description}</p>}

          <div className="rounded-lg border border-zinc-200 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("Who has it")}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <select
                className={cn(inputCls, "max-w-xs")}
                disabled={busy || !isOpen}
                value={d.assigned_to_user ?? ""}
                onChange={(e) => act("assign_ticket", { user: e.target.value || null })}
              >
                <option value="">{t("Unassigned")}</option>
                {staff.map((u) => (
                  <option key={u.user} value={u.user}>{u.name}</option>
                ))}
              </select>
              {isOpen && (
                <Button variant="outline" disabled={busy} onClick={() => act("claim_ticket", {})}>
                  {t("Assign to me")}
                </Button>
              )}
            </div>
            {d.assigned_to_user && d.assigned_at && (
              <p className="mt-1.5 text-xs text-zinc-500">
                {t("Assigned by {who} on {when}", { who: d.assigned_by_name || "-", when: String(d.assigned_at).slice(0, 16) })}
              </p>
            )}
            {!isOpen && (
              <p className="mt-2 text-sm text-zinc-700">
                {t("Solved by")}{" "}
                <span className="font-medium">{d.resolved_by_name || t("not recorded (before tracking)")}</span>
                {d.resolved_on ? ` · ${String(d.resolved_on).slice(0, 16)}` : ""}
                {d.resolution_note ? ` · ${d.resolution_note}` : ""}
              </p>
            )}
          </div>

          {isOpen ? (
            <div className="rounded-lg border border-zinc-200 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("Move it on")}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {d.status === "Open" && (
                  <Button variant="outline" disabled={busy} onClick={() => act("start_ticket", {})}>
                    {t("Start work")}
                  </Button>
                )}
                <input
                  className={cn(inputCls, "min-w-0 flex-1")}
                  placeholder={t("What was done? (kept with the ticket)")}
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                />
                <Button disabled={busy} onClick={() => act("resolve_ticket", { resolution_note: resolution }, () => setResolution(""))}>
                  {t("Mark solved")}
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-200 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("Came back?")}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  className={cn(inputCls, "min-w-0 flex-1")}
                  placeholder={t("Why is it being reopened?")}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <Button variant="outline" disabled={busy || reason.trim().length < 3} onClick={() => act("reopen_ticket", { reason }, () => setReason(""))}>
                  {t("Reopen")}
                </Button>
              </div>
            </div>
          )}

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("Timeline")}</p>
            <ol className="mt-2 space-y-3 border-s border-zinc-200 ps-4">
              {d.events.map((e, i) => (
                <li key={i} className="relative text-sm">
                  <span className="absolute -start-[21px] top-1.5 size-2 rounded-full bg-zinc-300" aria-hidden />
                  <p className="text-zinc-800">{eventText(e)}</p>
                  {e.note && e.kind !== "Created" && <p className="text-zinc-600">{e.note}</p>}
                  <p className="text-xs text-zinc-400">{String(e.at).slice(0, 16)}</p>
                </li>
              ))}
            </ol>
            <div className="mt-3 flex gap-2">
              <input
                className={cn(inputCls, "min-w-0 flex-1")}
                placeholder={t("Add a note: who was called, what was tried")}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <Button variant="outline" disabled={busy || !note.trim()} onClick={() => act("add_ticket_note", { note }, () => setNote(""))}>
                {t("Add note")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Sheet>
  )
}

export default function Tickets() {
  const { t } = useT()
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<Ticket[]>([])
  const [counts, setCounts] = useState<Counts | null>(null)
  const [view, setView] = useState<View>((params.get("view") as View) || "open")
  const [category, setCategory] = useState("")
  const [priority, setPriority] = useState("")
  const [q, setQ] = useState("")
  const [older, setOlder] = useState(0)
  const [staff, setStaff] = useState<Staff[]>([])
  const [selected, setSelected] = useState<string | null>(params.get("ticket"))
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rooms, setRooms] = useState<string[]>([])
  const [form, setForm] = useState({
    subject: "", category: "Housekeeping", priority: "Medium",
    room: "", description: "",
  })

  const load = useCallback(() => {
    call<{ tickets: Ticket[]; counts: Counts }>("kamra.tickets.tickets_search", {
      property: getCurrentProperty(),
      view,
      category: category || undefined,
      priority: priority || undefined,
      q: q || undefined,
      older_than_days: older || undefined,
    })
      .then((r) => {
        setRows(r.tickets)
        setCounts(r.counts)
      })
      .catch((e) => setError(serverError(e)))
  }, [view, category, priority, q, older])

  useEffect(() => {
    const h = setTimeout(load, q ? 250 : 0)
    return () => clearTimeout(h)
  }, [load, q])
  useRealtime(load)
  useEffect(() => {
    listResource("Room", { fields: ["name"], orderBy: "room_number asc" })
      .then((r) => setRooms(r.map((x) => x.name)))
    call<Staff[]>("kamra.tickets.ticket_assignees", { property: getCurrentProperty() })
      .then(setStaff)
      .catch(() => setStaff([]))
  }, [])

  function openTicket(name: string | null) {
    setSelected(name)
    const next = new URLSearchParams(params)
    if (name) next.set("ticket", name)
    else next.delete("ticket")
    setParams(next, { replace: true })
  }

  async function claim(ticket: string) {
    setBusy(ticket)
    setError(null)
    try {
      await call("kamra.tickets.claim_ticket", { ticket })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  async function create() {
    setBusy("new")
    setError(null)
    try {
      await call("kamra.api.create_ticket", {
        property: getCurrentProperty(),
        subject: form.subject,
        category: form.category,
        priority: form.priority,
        room: form.room || undefined,
        description: form.description || undefined,
      })
      setCreating(false)
      setForm({ subject: "", category: "Housekeeping", priority: "Medium", room: "", description: "" })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader className="items-start gap-4">
        <div className="min-w-0 flex-1">
          <CardTitle>{t("Service Tickets")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-500">
            {t("Guest requests with deadlines by priority - set them in Settings → Operations")}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="size-4" aria-hidden />
          {t("New ticket")}
        </Button>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="mb-3 flex flex-wrap gap-1.5" role="tablist">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              role="tab"
              aria-selected={view === v.id}
              onClick={() => setView(v.id)}
              className={cn(
                "rounded-full border px-3 py-1 text-sm",
                view === v.id ? "border-brand-600 bg-brand-50 text-brand-700" : "border-zinc-200 text-zinc-600 hover:bg-zinc-50",
              )}
            >
              {t(v.label)}
              {counts && <span className="ms-1.5 text-xs tabular-nums text-zinc-400">{counts[v.id]}</span>}
            </button>
          ))}
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            className={cn(inputCls, "w-56")}
            placeholder={t("Search subject, room, guest, id")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select className={cn(inputCls, "w-40")} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t("All categories")}</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{t(c)}</option>)}
          </select>
          <select className={cn(inputCls, "w-36")} value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">{t("Any priority")}</option>
            {["Low", "Medium", "High", "Urgent"].map((p) => <option key={p} value={p}>{t(p)}</option>)}
          </select>
          <select className={cn(inputCls, "w-48")} value={older} onChange={(e) => setOlder(Number(e.target.value))}>
            <option value={0}>{t("Any age")}</option>
            <option value={1}>{t("Open for over 1 day")}</option>
            <option value={3}>{t("Open for over 3 days")}</option>
            <option value={7}>{t("Open for over 7 days")}</option>
            <option value={30}>{t("Open for over 30 days")}</option>
          </select>
        </div>

        <ul className="divide-y divide-zinc-100">
          {rows.map((row) => {
            const isOpen = row.status === "Open" || row.status === "In Progress"
            return (
              <li key={row.name} className="flex flex-wrap items-center gap-3 py-3">
                <button
                  type="button"
                  onClick={() => openTicket(row.name)}
                  className={cn("min-w-0 flex-1 text-start", !isOpen && "opacity-70")}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{row.subject}</span>
                    <Badge tone={prioTone[row.priority] ?? "zinc"}>{t(row.priority)}</Badge>
                    <Badge tone="zinc">{t(row.category)}</Badge>
                    {row.source !== "Manual" && <Badge tone="brand">{t(row.source)}</Badge>}
                    {row.overdue && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-600">
                        <AlertTriangle className="size-3.5" aria-hidden />
                        {t("overdue by {t}", { t: human(row.minutes_left) })}
                      </span>
                    )}
                    {!row.overdue && isOpen && row.minutes_left != null && (
                      <span className="text-xs text-zinc-500">{t("{t} left", { t: human(row.minutes_left) })}</span>
                    )}
                    {Boolean(row.breached) && !isOpen && <span className="text-xs text-rose-400">{t("SLA breached")}</span>}
                  </div>
                  <div className="mt-0.5 text-xs text-zinc-500">
                    {row.name}
                    {row.room && ` · ${t("Room {n}", { n: row.room.split("-").pop() ?? "" })}`}
                    {row.guest_name && ` · ${row.guest_name}`}
                    {" · "}{t("open {t}", { t: human(Math.round(row.age_hours * 60)) })}
                    {" · "}
                    {isOpen
                      ? row.assigned_to_name || row.assigned_to_user
                        ? t("with {who}", { who: row.assigned_to_name || row.assigned_to_user || "" })
                        : t("unassigned")
                      : t("solved by {who}", { who: row.resolved_by_name || t("not recorded") })}
                  </div>
                </button>
                <div className="flex gap-2">
                  {isOpen && !row.assigned_to_user && (
                    <Button variant="outline" disabled={busy === row.name} onClick={() => claim(row.name)}>
                      {t("Take it")}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => openTicket(row.name)}>
                    {t("Open")}
                  </Button>
                </div>
              </li>
            )
          })}
          {rows.length === 0 && (
            <li className="py-10 text-center text-sm text-zinc-500">
              {view === "open" ? t("No open tickets - a quiet day at the desk.") : t("No tickets match.")}
            </li>
          )}
        </ul>
      </CardContent>

      {selected && (
        <TicketSheet name={selected} staff={staff} onClose={() => openTicket(null)} onChanged={load} />
      )}

      {creating && (
        <Sheet
          title={t("New ticket")}
          description={t("Guest request - SLA starts from priority at creation")}
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreating(false)}>
                {t("Cancel")}
              </Button>
              <Button
                disabled={busy === "new" || !form.subject}
                onClick={create}
              >
                {t("Create ticket")}
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Subject")}
              </span>
              <input
                className={inputCls}
                placeholder={t("What does the guest need?")}
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                autoFocus
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {t("Category")}
                </span>
                <select
                  className={inputCls}
                  value={form.category}
                  onChange={(e) =>
                    setForm({ ...form, category: e.target.value })
                  }
                >
                  {CATEGORIES.map((c) => (
                    <option key={c}>{t(c)}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {t("Priority")}
                </span>
                <select
                  className={inputCls}
                  value={form.priority}
                  onChange={(e) =>
                    setForm({ ...form, priority: e.target.value })
                  }
                >
                  {["Low", "Medium", "High", "Urgent"].map((p) => (
                    <option key={p}>{t(p)}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Room")}
              </span>
              <select
                className={inputCls}
                value={form.room}
                onChange={(e) => setForm({ ...form, room: e.target.value })}
              >
                <option value="">{t("No room")}</option>
                {rooms.map((r) => (
                  <option key={r} value={r}>
                    {t("Room {n}", { n: r.split("-").pop() ?? "" })}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                {t("Details")}
              </span>
              <textarea
                className={inputCls}
                rows={3}
                placeholder={t("Anything the staff should know (optional)")}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
          </div>
        </Sheet>
      )}
    </Card>
  )
}
