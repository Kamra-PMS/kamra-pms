import { Fragment, useCallback, useEffect, useState } from "react"
import {
  Bot,
  Check,
  Inbox,
  Loader2,
  Power,
  Users,
  X,
  Zap,
  MessageSquare,
  Plug,
  Sparkles,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useRealtime } from "../lib/realtime"
import Assistant from "./Assistant"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { cn } from "../lib/utils"
import { serverError } from "../lib/resource"


interface AutonomyRule {
  action_type: string
  autonomy: "Full" | "Suggest" | "Approve"
  threshold_field: string | null
  threshold_operator: string | null
  threshold_value: number | null
}

interface AgentRow {
  name: string
  agent_name: string
  persona: string
  active: 0 | 1
  property: string | null
  trigger_type: "Event" | "Cron" | "Webhook"
  schedule_cron: string | null
  channel: string
  model: string | null
  default_approver: string | null
  modified: string
  tools: string[]
  autonomy_rules: AutonomyRule[]
  last_action_at: string | null
  minutes_saved_week: number
  pending_count: number
}

interface PendingRow {
  name: string
  agent: string
  action_type: string
  status: string
  property: string | null
  summary: string
  action_endpoint: string
  reference_doctype: string | null
  reference_name: string | null
  requested_by: string | null
  action_log: string | null
  approver: string | null
  decision_note: string | null
  expires_at: string | null
  resolved_at: string | null
  creation: string
  before_snapshot?: Record<string, unknown> | null
  after_snapshot?: Record<string, unknown> | null
}


interface SavingsSummary {
  days: number
  channels: { channel: string; actions: number; minutes: number }[]
  total_minutes: number
  total_hours: number
}

const personaTone: Record<string, "brand" | "sky" | "amber" | "zinc" | "green"> = {
  "Front Desk Copilot": "brand",
  Revenue: "sky",
  Housekeeping: "green",
  "Voice Concierge": "amber",
  "WhatsApp Concierge": "green",
  "Night Auditor": "zinc",
  Sales: "sky",
  Collections: "amber",
  "Owner Digest": "brand",
  Custom: "zinc",
}

const statusTone: Record<string, "zinc" | "sky" | "amber" | "rose" | "green"> = {
  Executed: "green",
  Suggested: "sky",
  Pending: "amber",
  Approved: "green",
  Rejected: "rose",
  Expired: "zinc",
}

export default function Agents() {
  const property = getCurrentProperty()
  const [panel, setPanel] = useState<"none" | "connect">("none")

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="size-5 text-brand-600" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">Copilot</h1>
        </div>
        <p className="text-sm text-zinc-500">
          Chat with your PMS using your own AI key - it acts as you.
        </p>
        <div className="ml-auto flex items-center gap-2">
          {panel !== "none" && (
            <button
              onClick={() => setPanel("none")}
              className="flex items-center gap-1.5 rounded-full bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
            >
              <MessageSquare className="size-4" aria-hidden />
              Back to chat
            </button>
          )}
          <button
            onClick={() =>
              setPanel((p) => (p === "connect" ? "none" : "connect"))
            }
            title="Connect your own Claude to this hotel over MCP - scoped to your role"
            className={
              "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm " +
              (panel === "connect"
                ? "border-brand-400 bg-brand-50 text-brand-700"
                : "border-zinc-200 text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700")
            }
          >
            <Plug className="size-4" aria-hidden />
            Connect your AI
          </button>
        </div>
      </header>

      {panel === "connect" && <ConnectTab property={property} />}
      {panel === "none" && <Assistant />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Team tab
// ---------------------------------------------------------------------------

export function TeamTab({ property }: { property: string }) {
  const [rows, setRows] = useState<AgentRow[]>([])
  const [savings, setSavings] = useState<SavingsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      call<AgentRow[]>("kamra.agents_api.agents_list", {
        property,
        include_inactive: 1,
      }),
      call<SavingsSummary>("kamra.agents_api.agents_savings_summary", {
        property,
        days: 7,
      }),
    ])
      .then(([agents, s]) => {
        setRows(agents)
        setSavings(s)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
      .finally(() => setLoading(false))
  }, [property])

  useEffect(() => {
    load()
  }, [load])

  async function toggle(agent: AgentRow) {
    setBusy(agent.name)
    try {
      await call("kamra.agents_api.toggle_agent", {
        agent: agent.name,
        active: agent.active ? 0 : 1,
      })
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  if (loading && !rows.length) {
    return <LoadingRow />
  }

  return (
    <div className="space-y-4">
      {savings && <SavingsBanner s={savings} />}
      {error && <ErrorBanner message={error} />}
      {!rows.length && (
        <EmptyState
          icon={Users}
          title="No agents yet"
          note="Kamra seeds Front Desk Copilot, Night Auditor and Owner Digest on new-property install. Run the seed script to add them."
        />
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((agent) => (
          <AgentCard
            key={agent.name}
            agent={agent}
            busy={busy === agent.name}
            onToggle={() => toggle(agent)}
          />
        ))}
      </div>
    </div>
  )
}

export function SavingsBanner({ s }: { s: SavingsSummary }) {
  return (
    <Card className="border-brand-100 bg-brand-50/40">
      <CardContent className="flex flex-wrap items-center gap-4 py-4">
        <div className="flex items-center gap-2">
          <Zap className="size-5 text-brand-600" aria-hidden />
          <div>
            <div className="text-2xl font-semibold tracking-tight text-brand-700">
              {s.total_hours}h
            </div>
            <div className="text-xs text-brand-600/70">
              clerical time saved last {s.days} days
            </div>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          {s.channels.map((c) => (
            <span
              key={c.channel}
              className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-zinc-200"
            >
              {c.channel} · {c.actions} actions
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}


// Plain hotel lingo for the starter agents - what they do, not how.
const personaBlurb: Record<string, string> = {
  "Front Desk Copilot":
    "Answers and acts at the desk - quotes, bookings, check-ins, payments - whenever staff ask.",
  "Night Auditor":
    "Closes the day every night: posts room charges and flags no-shows, so nobody stays up for it.",
  "Owner Digest":
    "Sends the owner a plain-English summary of the week's numbers, every Sunday morning.",
}

function humanTrigger(a: AgentRow): string {
  if (a.trigger_type === "Event") return "Works on demand"
  if (a.trigger_type === "Webhook") return "Replies to messages"
  const c = (a.schedule_cron || "").trim()
  if (c === "0 3 * * *") return "Runs nightly at 3:00 am"
  if (c === "0 8 * * 0") return "Every Sunday, 8:00 am"
  return "Runs on a schedule"
}

export function AgentCard({
  agent,
  busy,
  onToggle,
}: {
  agent: AgentRow
  busy: boolean
  onToggle: () => void
}) {
  const tone = personaTone[agent.persona] ?? "zinc"
  return (
    <Card
      className={cn(
        !agent.active && "opacity-60",
        agent.pending_count > 0 && "ring-2 ring-amber-300",
      )}
    >
      <CardHeader className="space-y-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              {agent.agent_name}
              {agent.pending_count > 0 && (
                <Badge tone="amber">
                  {agent.pending_count} pending
                </Badge>
              )}
            </CardTitle>
            <div className="mt-0.5 text-xs text-zinc-500">
              {agent.persona}
              {agent.property ? ` · ${agent.property}` : " · Chain-global"}
            </div>
            {personaBlurb[agent.persona] && (
              <p className="mt-1.5 max-w-xs text-sm text-zinc-600">
                {personaBlurb[agent.persona]}
              </p>
            )}
          </div>
          <button
            onClick={onToggle}
            disabled={busy}
            aria-label={agent.active ? "Pause agent" : "Resume agent"}
            className={cn(
              "flex size-8 items-center justify-center rounded-full border transition",
              agent.active
                ? "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                : "border-zinc-300 bg-zinc-50 text-zinc-500 hover:bg-zinc-100",
            )}
          >
            {busy ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Power className="size-4" aria-hidden />
            )}
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={tone}>{humanTrigger(agent)}</Badge>
          <Badge tone="zinc">{agent.channel}</Badge>
        </div>

        <dl className="grid grid-cols-3 gap-2 text-xs">
          <Stat label="Tools" value={agent.tools.length} />
          <Stat label="Autonomy rules" value={agent.autonomy_rules.length} />
          <Stat
            label="Saved (7d)"
            value={formatMinutes(agent.minutes_saved_week)}
          />
        </dl>

        {agent.tools.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-zinc-500 hover:text-zinc-700">
              Show tools & rules
            </summary>
            <div className="mt-2 space-y-2">
              <div className="flex flex-wrap gap-1.5 text-zinc-400">
                {agent.trigger_type === "Cron" && agent.schedule_cron && (
                  <span>schedule: {agent.schedule_cron}</span>
                )}
                {agent.model && <span>model: {agent.model}</span>}
              </div>
              <ToolList tools={agent.tools} />
              <AutonomyList rules={agent.autonomy_rules} />
            </div>
          </details>
        )}

        {agent.last_action_at && (
          <div className="text-xs text-zinc-400">
            Last active {relativeTime(agent.last_action_at)}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-zinc-50 px-2 py-1.5">
      <div className="font-semibold text-zinc-800">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-400">
        {label}
      </div>
    </div>
  )
}

export function ToolList({ tools }: { tools: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {tools.map((t) => (
        <code
          key={t}
          className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[10px] text-zinc-700"
        >
          {t}
        </code>
      ))}
    </div>
  )
}

export function AutonomyList({ rules }: { rules: AutonomyRule[] }) {
  if (!rules.length) {
    return <p className="text-xs text-zinc-400">No overrides - all Full.</p>
  }
  return (
    <ul className="space-y-1 text-xs">
      {rules.map((r) => (
        <li key={r.action_type} className="flex flex-wrap items-baseline gap-2">
          <code className="font-mono text-[10px] text-zinc-500">
            {r.action_type}
          </code>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] font-semibold",
              r.autonomy === "Full" && "bg-emerald-50 text-emerald-700",
              r.autonomy === "Suggest" && "bg-sky-50 text-sky-700",
              r.autonomy === "Approve" && "bg-amber-50 text-amber-700",
            )}
          >
            {r.autonomy}
          </span>
          {r.threshold_field && (
            <span className="text-[10px] text-zinc-500">
              when {r.threshold_field} {r.threshold_operator} {r.threshold_value}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Inbox tab
// ---------------------------------------------------------------------------

export function InboxTab({ property }: { property: string }) {
  const [rows, setRows] = useState<PendingRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [note, setNote] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    call<PendingRow[]>("kamra.agents_api.pending_actions", {
      property,
    })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
      .finally(() => setLoading(false))
  }, [property])

  useEffect(() => {
    load()
  }, [load])

  async function approve(row: PendingRow) {
    setBusy(row.name)
    try {
      await call("kamra.agents_api.approve_action", {
        pending: row.name,
        note,
      })
      setNote("")
      setExpanded(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  async function reject(row: PendingRow) {
    setBusy(row.name)
    try {
      await call("kamra.agents_api.reject_action", {
        pending: row.name,
        reason: note,
      })
      setNote("")
      setExpanded(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  if (loading && !rows.length) return <LoadingRow />

  return (
    <div className="space-y-3">
      {error && <ErrorBanner message={error} />}
      {!rows.length && (
        <EmptyState
          icon={Inbox}
          title="Inbox is empty"
          note="Nothing waiting for your tap. Agents with Approve autonomy will land things here."
        />
      )}
      {rows.map((row) => (
        <Card key={row.name} className="border-amber-200">
          <CardContent className="space-y-3 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
                  {row.summary}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  <span>from {row.requested_by || row.agent}</span>
                  <span>·</span>
                  <span>{relativeTime(row.creation)}</span>
                  {row.reference_name && (
                    <>
                      <span>·</span>
                      <a
                        href={referenceLink(row)}
                        className="text-brand-600 hover:underline"
                      >
                        {row.reference_name}
                      </a>
                    </>
                  )}
                </div>
              </div>
              <Badge tone="amber">{row.action_type}</Badge>
            </div>

            {(row.before_snapshot || row.after_snapshot) && (
              <SnapshotDiff
                before={row.before_snapshot}
                after={row.after_snapshot}
              />
            )}

            {expanded === row.name ? (
              <div className="space-y-2 rounded-lg bg-zinc-50 p-3">
                <label className="block text-xs font-medium text-zinc-600">
                  Note (optional)
                </label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                  placeholder="Why you're approving or rejecting…"
                />
                <div className="flex gap-2">
                  <Button
                    onClick={() => approve(row)}
                    disabled={busy === row.name}
                  >
                    {busy === row.name ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : (
                      <Check className="size-4" aria-hidden />
                    )}
                    Approve & run
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => reject(row)}
                    disabled={busy === row.name}
                  >
                    <X className="size-4" aria-hidden />
                    Reject
                  </Button>
                  <button
                    className="ml-auto text-xs text-zinc-500 hover:text-zinc-700"
                    onClick={() => {
                      setExpanded(null)
                      setNote("")
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <Button variant="outline" onClick={() => setExpanded(row.name)}>
                Review
              </Button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function SnapshotDiff({
  before,
  after,
}: {
  before?: Record<string, unknown> | null
  after?: Record<string, unknown> | null
}) {
  const beforeStr = before ? JSON.stringify(before, null, 2) : "-"
  const afterStr = after ? JSON.stringify(after, null, 2) : "(pending - not yet applied)"
  return (
    <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          Before
        </div>
        <pre className="max-h-40 overflow-auto rounded-md bg-zinc-50 p-2 font-mono text-[11px] text-zinc-700">
          {beforeStr}
        </pre>
      </div>
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          After (proposed)
        </div>
        <pre className="max-h-40 overflow-auto rounded-md bg-amber-50 p-2 font-mono text-[11px] text-amber-800">
          {afterStr}
        </pre>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Timeline tab
// ---------------------------------------------------------------------------

function LoadingRow() {
  return (
    <p className="py-10 text-center text-sm text-zinc-400">
      <Loader2 className="mr-2 inline size-4 animate-spin" aria-hidden />
      Loading…
    </p>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
      {message}
    </div>
  )
}

function EmptyState({
  icon: Icon,
  title,
  note,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  note: string
}) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 py-10 text-center">
      <Icon className="mx-auto mb-2 size-6 text-zinc-400" aria-hidden />
      <p className="text-sm font-medium text-zinc-700">{title}</p>
      <p className="mt-1 text-xs text-zinc-500">{note}</p>
    </div>
  )
}

function formatMinutes(min: number): string {
  if (!min) return "-"
  if (min < 60) return `${Math.round(min)}m`
  return `${(min / 60).toFixed(1)}h`
}

function relativeTime(iso: string | null): string {
  if (!iso) return ""
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = Math.max(0, now - then)
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

function referenceLink(row: {
  reference_doctype: string | null
  reference_name: string | null
}): string {
  const dt = row.reference_doctype
  const name = row.reference_name
  if (!dt || !name) return "#"
  if (dt === "Reservation") return `/reservations?q=${encodeURIComponent(name)}`
  if (dt === "Folio") return `/billing/${encodeURIComponent(name)}`
  if (dt === "Guest") return `/guests/${encodeURIComponent(name)}`
  if (dt === "Season") return `/seasons`
  if (dt === "Service Ticket") return `/tickets`
  return "#"
}

// ---------------------------------------------------------------------------
// Activity tab - the one ledger: everything anyone did, human or AI
// ---------------------------------------------------------------------------

interface ActivityRow {
  name: string
  creation: string
  actor: string | null
  agent_name: string | null
  action_type: string
  action_channel: string
  approval_status: string
  approver: string | null
  reference_doctype: string | null
  reference_name: string | null
  rationale: string
  minutes_saved: number
}

interface ActivityDetail extends ActivityRow {
  executed_at: string | null
  property: string
  autonomy: string | null
  before_snapshot: unknown
  after_snapshot: unknown
}

const prettyAction = (t: string) =>
  t.replace(/^copilot_/, "").replace(/_/g, " ")

const fmtWhen = (d: string) =>
  new Date(d.replace(" ", "T")).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  })

export function ActivityTab({ property }: { property: string }) {
  const [rows, setRows] = useState<ActivityRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState("")
  const [page, setPage] = useState(0)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [detail, setDetail] = useState<ActivityDetail | null>(null)
  const PAGE = 50

  const toggleRow = (rowName: string) => {
    if (expanded === rowName) {
      setExpanded(null)
      return
    }
    setExpanded(rowName)
    setDetail(null)
    call<ActivityDetail>("kamra.agents_api.activity_detail", { name: rowName })
      .then(setDetail)
      .catch(() => setDetail(null))
  }

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    call<ActivityRow[]>("kamra.agents_api.activity_feed", {
      property,
      actor_kind: kind || null,
      limit: PAGE,
      start: page * PAGE,
    })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
      .finally(() => { if (!silent) setLoading(false) })
  }, [property, kind, page])

  // live audit stream: refetch silently on any change (no loading flash)
  useRealtime(useCallback(() => load(true), [load]))

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={kind}
          onChange={(e) => {
            setKind(e.target.value)
            setPage(0)
          }}
          className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"
          aria-label="Filter by who acted"
        >
          <option value="">Everyone</option>
          <option value="human">People only</option>
          <option value="agent">AI only</option>
        </select>
        <p className="text-xs text-zinc-400">
          Every action on the property, newest first - who did it and what
          changed.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      {loading ? (
        <LoadingRow />
      ) : rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-400">
          Nothing logged yet.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2">Who</th>
                <th className="px-3 py-2">What</th>
                <th className="px-3 py-2">On</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((r) => (
                <Fragment key={r.name}>
                <tr
                  className="cursor-pointer hover:bg-zinc-50"
                  onClick={() => toggleRow(r.name)}
                >
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-zinc-500">
                    {fmtWhen(r.creation)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {r.agent_name ? (
                      <span className="inline-flex items-center gap-1">
                        <Bot className="size-3.5 text-brand-600" aria-hidden />
                        <span className="font-medium">{r.agent_name}</span>
                      </span>
                    ) : (
                      <span className="font-medium">
                        {(r.actor ?? "system").split("@")[0]}
                      </span>
                    )}
                  </td>
                  <td className="max-w-md px-3 py-2">
                    <span className="font-medium capitalize">
                      {prettyAction(r.action_type)}
                    </span>
                    {r.rationale && (
                      <span className="text-zinc-500"> - {r.rationale}</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-zinc-400">
                    {r.reference_name ?? "-"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Badge tone={statusTone[r.approval_status] ?? "zinc"}>
                      {r.approval_status}
                    </Badge>
                    {r.approver && (
                      <span className="ml-1 text-xs text-zinc-400">
                        by {r.approver.split("@")[0]}
                      </span>
                    )}
                  </td>
                </tr>
                {expanded === r.name && (
                  <tr className="bg-zinc-50/60">
                    <td colSpan={5} className="px-4 py-3">
                      {!detail ? (
                        <p className="text-xs text-zinc-400">Loading…</p>
                      ) : (
                        <div className="space-y-3 text-sm">
                          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-4">
                            {([
                              ["Logged", fmtWhen(detail.creation)],
                              ["Executed", detail.executed_at ? fmtWhen(detail.executed_at) : "-"],
                              ["Actor", detail.actor ?? "system"],
                              ["Agent", detail.agent_name ?? "-"],
                              ["Channel", detail.action_channel ?? "-"],
                              ["Autonomy", detail.autonomy ?? "-"],
                              [
                                "Reference",
                                detail.reference_name
                                  ? `${detail.reference_doctype} · ${detail.reference_name}`
                                  : "-",
                              ],
                              [
                                "Minutes saved",
                                detail.minutes_saved ? String(detail.minutes_saved) : "-",
                              ],
                            ] as [string, string][]).map(([k, v]) => (
                              <div key={k}>
                                <dt className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                                  {k}
                                </dt>
                                <dd className="text-zinc-700">{v}</dd>
                              </div>
                            ))}
                          </dl>
                          {detail.rationale && (
                            <p className="text-zinc-600">
                              <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                                Why:{" "}
                              </span>
                              {detail.rationale}
                            </p>
                          )}
                          {(detail.before_snapshot || detail.after_snapshot) != null && (
                            <div className="grid gap-3 sm:grid-cols-2">
                              {(
                                [
                                  ["Before", detail.before_snapshot],
                                  ["After", detail.after_snapshot],
                                ] as [string, unknown][]
                              ).map(([label, snap]) =>
                                snap == null ? null : (
                                  <div key={label as string}>
                                    <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                                      {label}
                                    </p>
                                    <pre className="max-h-56 overflow-auto rounded-lg border border-zinc-200 bg-white p-2.5 text-xs leading-relaxed text-zinc-700">
                                      {typeof snap === "string"
                                        ? snap
                                        : JSON.stringify(snap, null, 2)}
                                    </pre>
                                  </div>
                                ),
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex items-center justify-between text-sm text-zinc-500">
        <span>Page {page + 1}</span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Prev
          </Button>
          <Button
            variant="outline"
            disabled={rows.length < PAGE}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Connect tab - bring your own Claude: personal, role-scoped MCP credentials
// ---------------------------------------------------------------------------

interface ConnectorCreds {
  api_key: string
  api_secret: string
  base_url: string
  property: string
  user: string
}

export function ConnectTab({ property }: { property: string }) {
  const [creds, setCreds] = useState<ConnectorCreds | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const snippet = creds
    ? JSON.stringify(
        {
          mcpServers: {
            kamra: {
              command: "python",
              args: ["apps/kamra/mcp/kamra_mcp.py"],
              env: {
                KAMRA_URL: creds.base_url,
                KAMRA_API_KEY: creds.api_key,
                KAMRA_API_SECRET: creds.api_secret,
                KAMRA_PROPERTY: creds.property,
              },
            },
          },
        },
        null,
        2,
      )
    : ""

  return (
    <div className="max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Claude Desktop</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-500">
              Connect Claude to this hotel like any connector. It acts as YOU:
              your role decides what it can see and do - a front desk
              connection books and checks in; it cannot touch rates or
              finance. Every action lands in Activity under your name.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {!creds ? (
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                setError(null)
                try {
                  const r = await call<ConnectorCreds>(
                    "kamra.api.my_connector_credentials",
                    { property },
                  )
                  setCreds(r)
                } catch (e) {
                  setError(serverError(e))
                } finally {
                  setBusy(false)
                }
              }}
            >
              Generate my connection
            </Button>
          ) : (
            <>
              <p className="text-sm text-zinc-600">
                Paste this into your{" "}
                <code className="rounded bg-zinc-100 px-1">
                  claude_desktop_config.json
                </code>{" "}
                (Claude Desktop → Settings → Developer → Edit Config), then
                restart Claude:
              </p>
              <pre className="overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs leading-relaxed text-zinc-700">
                {snippet}
              </pre>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(snippet)
                    setCopied(true)
                    setTimeout(() => setCopied(false), 1500)
                  }}
                >
                  {copied ? "Copied" : "Copy config"}
                </Button>
                <span className="text-xs text-amber-600">
                  The secret is shown once - regenerating invalidates the old
                  one.
                </span>
              </div>
              <p className="text-xs text-zinc-500">
                Then ask Claude things like "occupancy this week", "build me an
                MIS report from today's numbers", or "book a Deluxe for
                Friday" - it uses Kamra's governed tools with your
                permissions.
              </p>
            </>
          )}
          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-zinc-400">
        Need a platform-wide or service key (all properties, custom scope)?
        That is issued by your system admin under Developers.
      </p>
    </div>
  )
}
