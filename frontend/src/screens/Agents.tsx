import { Fragment, useCallback, useEffect, useState } from "react"
import {
  Bot,
  Copy,
  ExternalLink,
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
          Chat in the console, or connect Claude — it acts as you, with your
          role limits, on the same governed tools.
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
            title="Open Claude and connect this hotel over MCP — scoped to your role"
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
// Connect tab — one click into Claude's prefilled connector dialog + OAuth
// ---------------------------------------------------------------------------

interface ConnectInfo {
  mcp_url: string
  claude_install_url: string
  claude_code: string
  is_public_https: boolean
  property: string
  property_name: string
  user: string
  tool_count: number
  active_grants: number
  last_mcp: { creation: string; action_type: string } | null
}

export function ConnectTab({ property }: { property: string }) {
  const [info, setInfo] = useState<ConnectInfo | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<"url" | "code" | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setInfo(
        await call<ConnectInfo>("kamra.mcp_oauth.connect_info", { property }),
      )
    } catch (e) {
      setError(serverError(e))
    }
  }, [property])

  useEffect(() => {
    void load()
  }, [load])

  function markCopied(which: "url" | "code", text: string) {
    navigator.clipboard.writeText(text)
    setCopied(which)
    setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div className="max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Connect Claude</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-500">
              Claude acts as you at {info?.property_name || "this hotel"}: your
              role decides what it can see and do. A front-desk connection
              books and checks in; it cannot touch rates or finance. Every
              action lands in Activity under your name.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {info && !info.is_public_https && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Claude reaches this hotel from Anthropic&apos;s cloud, so the
              site needs public HTTPS. This origin looks local — use Claude
              Code over HTTP on this machine, or the stdio sidecar, until you
              have a public URL.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={!info?.claude_install_url}
              onClick={() => {
                if (!info) return
                window.open(info.claude_install_url, "_blank", "noopener")
              }}
            >
              <ExternalLink className="size-4" aria-hidden />
              Connect Claude
            </Button>
            {info && info.active_grants > 0 && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={async () => {
                  if (
                    !confirm(
                      "Disconnect Claude? It will have to sign in again.",
                    )
                  )
                    return
                  setBusy(true)
                  try {
                    await call("kamra.mcp_oauth.revoke_my_grants", {
                      property,
                    })
                    await load()
                  } catch (e) {
                    setError(serverError(e))
                  } finally {
                    setBusy(false)
                  }
                }}
              >
                Disconnect
              </Button>
            )}
          </div>
          {info?.last_mcp && (
            <p className="text-xs text-zinc-500">
              Last MCP action: {prettyAction(info.last_mcp.action_type)} ·{" "}
              {fmtWhen(info.last_mcp.creation)}
            </p>
          )}
          {info && info.active_grants > 0 && !info.last_mcp && (
            <p className="text-xs text-green-700">
              Claude is authorised for this property. Enable the connector in
              a chat with the + menu, then talk in hotel language.
            </p>
          )}
          <p className="text-sm text-zinc-600">
            Claude opens with this hotel&apos;s MCP URL filled in. Confirm Add,
            sign in here if asked, pick the property, Allow. Then in Claude
            enable the connector on the chat + menu and say things like
            &quot;occupancy this week&quot; or &quot;book a Deluxe for
            Friday&quot;.
          </p>
          {info && (
            <>
              <div>
                <div className="mb-1 text-xs font-medium text-zinc-500">
                  MCP URL · {info.tool_count} governed tools
                </div>
                <div className="flex items-stretch gap-2">
                  <code className="flex-1 overflow-x-auto rounded-lg bg-zinc-100 px-3 py-2 font-mono text-xs text-zinc-800">
                    {info.mcp_url}
                  </code>
                  <Button
                    variant="outline"
                    onClick={() => markCopied("url", info.mcp_url)}
                  >
                    <Copy className="size-3.5" aria-hidden />
                    {copied === "url" ? "Copied" : "Copy"}
                  </Button>
                </div>
              </div>
              <div>
                <div className="mb-1 text-xs font-medium text-zinc-500">
                  Claude Code
                </div>
                <div className="flex items-stretch gap-2">
                  <pre className="flex-1 overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs leading-relaxed text-zinc-700">
                    {info.claude_code}
                  </pre>
                  <Button
                    variant="outline"
                    onClick={() => markCopied("code", info.claude_code)}
                  >
                    <Copy className="size-3.5" aria-hidden />
                    {copied === "code" ? "Copied" : "Copy"}
                  </Button>
                </div>
              </div>
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
        Need a platform-wide or service key (HeyKoala, unattended jobs)? That
        is issued by your system admin under Developers. Staff should use
        Connect Claude — no API secrets on a laptop.
      </p>
    </div>
  )
}
