import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Search, ShieldCheck, Unplug } from "lucide-react"

import { Badge } from "../../components/ui/badge"
import { Button } from "../../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card"
import { call, getCurrentProperty } from "../../lib/api"
import { useT, uiDateLocale } from "../../lib/i18n"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"
import { inputCls, Switch } from "./ModulePage"


/** Settings, AI access (MCP): who may connect Claude or another MCP client,
 *  what the AI may do at this property, and the live connections. MCP Read
 *  and MCP Manage only open the door: each person's normal roles still
 *  decide what a tool can see or change. Changes apply on the next call. */

type Level = "none" | "read" | "manage" | "admin"

interface StaffAccess {
  user: string
  full_name: string
  email: string
  enabled: number
  roles: string[]
  is_self: boolean
  level: Level
  editable: boolean
}

interface Connection {
  name: string
  user: string
  full_name: string
  client_name: string
  created: string | null
  last_used: string | null
}

interface Overview {
  property: string
  property_name: string
  site_disabled: boolean
  enabled: boolean
  read_only: boolean
  blocked_tools: string[]
  tools: { name: string; group: string; mutating: boolean }[]
  staff: StaffAccess[]
  connections: Connection[]
  recent: { name: string; creation: string; actor: string; action_type: string }[]
  redirect_uris: string[]
  can_edit_redirects: boolean
}

const LEVELS: { value: Exclude<Level, "admin">; label: string }[] = [
  { value: "none", label: "No access" },
  { value: "read", label: "MCP Read" },
  { value: "manage", label: "MCP Manage" },
]

function when(d: string | null): string {
  if (!d) return "-"
  const dt = new Date(d.replace(" ", "T"))
  return dt.toLocaleString(uiDateLocale(undefined), {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  })
}

export function McpAccessPage() {
  const { t } = useT()
  const property = getCurrentProperty()
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [toolQ, setToolQ] = useState("")
  const [redirects, setRedirects] = useState("")

  const load = useCallback(() => {
    if (!property) return
    call<Overview>("kamra.mcp_access.access_overview", { property })
      .then((d) => {
        setData(d)
        setRedirects(d.redirect_uris.join("\n"))
      })
      .catch((e) => setError(serverError(e)))
  }, [property])
  useEffect(load, [load])

  const run = async (key: string, fn: () => Promise<unknown>, done?: string) => {
    setBusy(key)
    setError(null)
    setNotice(null)
    try {
      await fn()
      if (done) setNotice(done)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(null)
    }
  }

  const setPolicy = (changes: Record<string, unknown>) =>
    run("policy", () => call("kamra.mcp_access.set_mcp_policy", { property, ...changes }))

  const shownStaff = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data?.staff ?? []).filter(
      (s) => Boolean(Number(s.enabled)) &&
        (!needle || s.full_name.toLowerCase().includes(needle) || s.email.toLowerCase().includes(needle)),
    )
  }, [data, q])

  const shownTools = useMemo(() => {
    const needle = toolQ.trim().toLowerCase()
    return (data?.tools ?? []).filter(
      (tool) => !needle || tool.name.includes(needle) || tool.group.toLowerCase().includes(needle),
    )
  }, [data, toolQ])

  if (error && !data) return <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{t(error)}</p>
  if (!data) return <p className="py-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>

  const blocked = new Set(data.blocked_tools)
  const toggleTool = (name: string) => {
    const next = new Set(blocked)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setPolicy({ blocked_tools: JSON.stringify([...next]) })
  }

  return (
    <div className="space-y-4">
      {data.site_disabled && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("MCP is turned off for this whole site (kamra_mcp_disabled), so nothing below takes effect until IT turns it back on.")}
        </p>
      )}
      {notice && <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{t(error)}</p>}

      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t("AI access at this property")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Claude and other MCP clients act as the person who connected them, within that person's roles, and every change lands in Activity under their name.")}
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-medium text-zinc-800">{t("AI access over MCP")}</p>
              <p className="text-xs text-zinc-500">{t("Off: nobody can connect an AI client to this property, and existing connections stop working.")}</p>
            </div>
            <Switch on={data.enabled} label="AI access over MCP" disabled={busy === "policy"}
              onToggle={() => setPolicy({ enabled: data.enabled ? 0 : 1 })} />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-medium text-zinc-800">{t("Block write tools")}</p>
              <p className="text-xs text-zinc-500">{t("AI clients can look but never change anything here, even for people with MCP Manage.")}</p>
            </div>
            <Switch on={data.read_only} label="Block write tools" disabled={busy === "policy"}
              onToggle={() => setPolicy({ read_only: data.read_only ? 0 : 1 })} />
          </div>
          <p className="text-xs text-zinc-500">
            {t("In Claude, set write tools to Needs approval as well: Kamra marks every tool as read-only or as making changes, and the destructive ones (cancel, void, check-out, night audit) separately.")}
          </p>
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader>
          <div>
            <CardTitle>{t("Who can use MCP")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("MCP Read lets the AI look; MCP Manage also lets it make changes. Hotel admins and IT always have full access. A person never gets more through the AI than their own roles allow. A change applies to their next request, no reconnect needed.")}
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <input className={cn(inputCls, "ps-9")} placeholder={t("Search name or email")}
              value={q} onChange={(e) => setQ(e.target.value)} aria-label={t("Search staff")} />
          </div>
          <ul className="divide-y divide-zinc-100">
            {shownStaff.map((s) => (
              <li key={s.user} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-800">{s.full_name || s.email}</p>
                  <p className="truncate text-xs text-zinc-500">{s.email} · {s.roles.map((r) => t(r)).join(", ")}</p>
                </div>
                {s.level === "admin" ? (
                  <Badge tone="brand">{t("Full access (admin)")}</Badge>
                ) : (
                  <select
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
                    value={s.level}
                    disabled={!s.editable || s.is_self || busy === s.user}
                    aria-label={t("AI access for {name}", { name: s.full_name || s.email })}
                    onChange={(e) => run(s.user, () => call("kamra.mcp_access.set_mcp_level", {
                      property, user: s.user, level: e.target.value,
                    }), t("AI access updated for {name}.", { name: s.full_name || s.email }))}
                  >
                    {LEVELS.map((l) => <option key={l.value} value={l.value}>{t(l.label)}</option>)}
                  </select>
                )}
              </li>
            ))}
            {shownStaff.length === 0 && <li className="py-6 text-center text-sm text-zinc-400">{t("No one matches.")}</li>}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t("Connected AI clients")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">{t("Each sign-in from Claude, ChatGPT or another MCP client. Disconnect one and it has to sign in again.")}</p>
          </div>
        </CardHeader>
        <CardContent>
          {data.connections.length === 0 ? (
            <p className="py-4 text-sm text-zinc-400">{t("No AI client is connected to this property.")}</p>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {data.connections.map((c) => (
                <li key={c.name} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium text-zinc-800">{c.client_name} · {c.full_name}</p>
                    <p className="text-xs text-zinc-500">
                      {t("Connected {when}", { when: when(c.created) })} · {t("Last used {when}", { when: when(c.last_used) })}
                    </p>
                  </div>
                  <Button variant="outline" disabled={busy === c.name}
                    onClick={() => run(c.name, () => call("kamra.mcp_access.revoke_connection", {
                      property, grant: c.name,
                    }), t("Disconnected."))}>
                    <Unplug className="size-4" aria-hidden />{t("Disconnect")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-zinc-500">
            <Link to="/activity" className="font-medium text-brand-700 hover:underline">{t("See every AI action in Activity")}</Link>
            {data.recent.length > 0 && <> · {t("Last: {action} by {actor}, {when}", {
              action: data.recent[0].action_type, actor: data.recent[0].actor, when: when(data.recent[0].creation),
            })}</>}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t("Blocked tools")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">{t("Switch off single tools for AI clients at this property. Staff can still do the same thing in Kamra.")}</p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <input className={inputCls} placeholder={t("Find a tool")} value={toolQ}
            onChange={(e) => setToolQ(e.target.value)} aria-label={t("Find a tool")} />
          <ul className="grid max-h-80 gap-1 overflow-y-auto sm:grid-cols-2">
            {shownTools.map((tool) => (
              <li key={tool.name} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-zinc-50">
                <span className="min-w-0 truncate text-sm">
                  <code className="text-xs">{tool.name}</code>
                  <span className="ms-2 text-xs text-zinc-400">{t(tool.group)}</span>
                  {tool.mutating && <Badge tone="amber" className="ms-2">{t("changes data")}</Badge>}
                </span>
                <Switch on={!blocked.has(tool.name)} label={tool.name} disabled={busy === "policy"}
                  onToggle={() => toggleTool(tool.name)} />
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2"><ShieldCheck className="size-4 text-zinc-400" aria-hidden />{t("Extra sign-in addresses")}</CardTitle>
            <p className="mt-0.5 text-xs text-zinc-400">
              {t("Claude, Claude Code and ChatGPT work out of the box. For another client, such as your own n8n, add its exact OAuth redirect address: https only, no wildcards, one per line. Applies to every property on this site.")}
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea className={cn(inputCls, "min-h-24 font-mono text-xs")} value={redirects}
            disabled={!data.can_edit_redirects}
            placeholder="https://n8n.yourhotel.com/rest/oauth2-credential/callback"
            onChange={(e) => setRedirects(e.target.value)} aria-label={t("Extra sign-in addresses")} />
          {data.can_edit_redirects ? (
            <Button disabled={busy === "redirects"}
              onClick={() => run("redirects", () => call("kamra.mcp_access.set_extra_redirect_uris", {
                uris: JSON.stringify(redirects.split("\n").map((u) => u.trim()).filter(Boolean)),
              }), t("Saved."))}>
              {t("Save addresses")}
            </Button>
          ) : (
            <p className="text-xs text-zinc-500">{t("Only IT can change these.")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
