import { Fragment, useCallback, useEffect, useState } from "react"
import {
  Bot,
  Loader2,
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
import { serverError } from "../lib/resource"
import { moneyLocale } from "../lib/money"



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
          <h1 className="text-xl font-semibold tracking-tight">Kamra Agent</h1>
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

function LoadingRow() {
  return (
    <p className="py-10 text-center text-sm text-zinc-400">
      <Loader2 className="mr-2 inline size-4 animate-spin" aria-hidden />
      Loading…
    </p>
  )
}

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
  new Date(d.replace(" ", "T")).toLocaleString(moneyLocale(), {
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
