import { useCallback, useEffect, useState } from "react"
import { AlarmClock } from "lucide-react"
import { Link } from "react-router-dom"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT, t as translate } from "../lib/i18n"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Badge } from "../components/ui/badge"


interface Group {
  label: string
  count: number
  resolved: number
  breached: number
  breach_pct: number
  avg_resolve_mins: number | null
}
interface Overdue {
  name: string
  subject?: string
  assigned_to_user?: string | null
  category: string
  priority: string
  overdue_hours: number
}
interface Solver {
  user: string | null
  name: string
  resolved: number
  breached: number
  avg_resolve_mins: number | null
}
interface OldOpen {
  name: string
  subject: string
  category: string
  priority: string
  status: string
  age_days: number
  assigned_to_user: string | null
  assigned_to_name: string | null
}
interface Sla {
  from: string
  to: string
  total: number
  resolved: number
  open: number
  breached: number
  breach_pct: number
  avg_resolve_mins: number | null
  by_category: Group[]
  by_priority: Group[]
  overdue: Overdue[]
  by_resolver: Solver[]
  aging: { label: string; count: number }[]
  oldest_open: OldOpen[]
  open_total: number
  unassigned_open: number
}

const ticketLink = (name: string) => `/tickets?ticket=${encodeURIComponent(name)}`

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function humanMins(m: number | null): string {
  if (m == null) return "-"
  if (m < 60) return `${m} min`
  const h = m / 60
  return h < 24 ? `${h.toFixed(1)} h` : `${(h / 24).toFixed(1)} d`
}

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function breachTone(pct: number): "rose" | "amber" | "brand" {
  return pct >= 25 ? "rose" : pct >= 10 ? "amber" : "brand"
}

export default function OpsSLA() {
  const { t } = useT()
  const [from, setFrom] = useState(isoDaysAgo(30))
  const [to, setTo] = useState(new Date().toISOString().slice(0, 10))
  const [data, setData] = useState<Sla | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Sla>("kamra.reports.sla_report", {
      property: getCurrentProperty(),
      from_date: from,
      to_date: to,
    })
      .then((d) => {
        setData(d)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
  }, [from, to])

  useEffect(load, [load])

  const GroupTable = ({ title, rows }: { title: string; rows: Group[] }) => (
    <Card>
      <CardHeader>
        <CardTitle>{translate(title)}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-400">{translate("No tickets.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="py-2 pr-3">{title.includes("category") ? translate("Category") : translate("Priority")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Tickets")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Resolved")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Breached")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Breach %")}</th>
                  <th className="py-2 text-right">{translate("Avg resolve")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((r) => (
                  <tr key={r.label}>
                    <td className="py-2 pr-3 font-medium">{translate(r.label)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.count}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.resolved}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.breached}</td>
                    <td className="py-2 pr-3 text-right">
                      <Badge tone={breachTone(r.breach_pct)}>{r.breach_pct}%</Badge>
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {humanMins(r.avg_resolve_mins)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
            <AlarmClock className="size-5 text-brand-600" />{translate("Operations SLA")}</h1>
          <p className="text-xs text-zinc-500">{translate("Are guest requests being resolved inside their promised window?")}</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <input type="date" className={inputCls} value={from}
            onChange={(e) => setFrom(e.target.value)} />
          <span className="text-zinc-400">→</span>
          <input type="date" className={inputCls} value={to}
            onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Tickets", String(data.total), "text-zinc-800"],
              ["Resolved", `${data.resolved} / ${data.total}`, "text-zinc-800"],
              [
                t("Breach rate"),
                `${data.breach_pct}%`,
                data.breach_pct >= 25 ? "text-rose-600" : data.breach_pct >= 10 ? "text-amber-600" : "text-brand-600",
              ],
              ["Avg resolve", humanMins(data.avg_resolve_mins), "text-zinc-800"],
              ["Open now (all time)", String(data.open_total), "text-zinc-800"],
              ["Unassigned", String(data.unassigned_open), data.unassigned_open ? "text-amber-600" : "text-zinc-800"],
            ].map(([label, val, tone]) => (
              <Card key={label}>
                <CardContent className="p-4">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                    {translate(label)}
                  </div>
                  <div className={`mt-1 text-2xl font-bold ${tone}`}>{val}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <GroupTable title={translate("By category")} rows={data.by_category} />
            <GroupTable title={translate("By priority")} rows={data.by_priority} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{translate("Overdue now")}{data.overdue.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-rose-600">
                    {data.overdue.length}{translate(" past due")}</span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.overdue.length === 0 ? (
                <p className="py-6 text-center text-sm text-zinc-400">{translate("Nothing overdue - every open request is inside its window.")}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        <th className="py-2 pr-3">{translate("Ticket")}</th>
                        <th className="py-2 pr-3">{translate("Subject")}</th>
                        <th className="py-2 pr-3">{translate("With")}</th>
                        <th className="py-2 pr-3">{translate("Category")}</th>
                        <th className="py-2 pr-3">{translate("Priority")}</th>
                        <th className="py-2 text-right">{translate("Overdue by")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {data.overdue.map((o) => (
                        <tr key={o.name}>
                          <td className="py-2 pr-3 font-mono text-xs">
                            <Link to={ticketLink(o.name)} className="text-brand-700 hover:underline">{o.name}</Link>
                          </td>
                          <td className="py-2 pr-3">{o.subject ?? ""}</td>
                          <td className="py-2 pr-3">{o.assigned_to_user ?? <span className="text-amber-600">{translate("Unassigned")}</span>}</td>
                          <td className="py-2 pr-3">{translate(o.category)}</td>
                          <td className="py-2 pr-3">{o.priority}</td>
                          <td className="py-2 text-right tabular-nums text-rose-600">
                            {o.overdue_hours}{translate(" h")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{translate("Solved by")}</CardTitle>
              </CardHeader>
              <CardContent>
                {data.by_resolver.length === 0 ? (
                  <p className="py-6 text-center text-sm text-zinc-400">{translate("No tickets solved in this window.")}</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        <th className="py-2 pr-3">{translate("Person")}</th>
                        <th className="py-2 pr-3 text-right">{translate("Solved")}</th>
                        <th className="py-2 pr-3 text-right">{translate("Late")}</th>
                        <th className="py-2 text-right">{translate("Avg time")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {data.by_resolver.map((r) => (
                        <tr key={r.user ?? "none"}>
                          <td className="py-2 pr-3 font-medium">{r.name}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{r.resolved}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{r.breached}</td>
                          <td className="py-2 text-right tabular-nums">{humanMins(r.avg_resolve_mins)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="mt-2 text-xs text-zinc-400">{translate("Tickets solved before tracking began show as \"Not recorded\".")}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{translate("How long open tickets have waited")}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-4 gap-2">
                  {data.aging.map((a) => (
                    <div key={a.label} className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                      <div className={`text-xl font-bold tabular-nums ${a.label === "Over 7 days" && a.count ? "text-rose-600" : "text-zinc-800"}`}>
                        {a.count}
                      </div>
                      <div className="text-[11px] text-zinc-500">{translate(a.label)}</div>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-zinc-400">{translate("Every ticket still open, whatever the date range above.")}</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{translate("Oldest open tickets")}</CardTitle>
            </CardHeader>
            <CardContent>
              {data.oldest_open.length === 0 ? (
                <p className="py-6 text-center text-sm text-zinc-400">{translate("Nothing is waiting.")}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        <th className="py-2 pr-3">{translate("Ticket")}</th>
                        <th className="py-2 pr-3">{translate("Subject")}</th>
                        <th className="py-2 pr-3">{translate("Priority")}</th>
                        <th className="py-2 pr-3">{translate("With")}</th>
                        <th className="py-2 text-right">{translate("Open for")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {data.oldest_open.map((o) => (
                        <tr key={o.name}>
                          <td className="py-2 pr-3 font-mono text-xs">
                            <Link to={ticketLink(o.name)} className="text-brand-700 hover:underline">{o.name}</Link>
                          </td>
                          <td className="py-2 pr-3">{o.subject}</td>
                          <td className="py-2 pr-3">{o.priority}</td>
                          <td className="py-2 pr-3">{o.assigned_to_name ?? o.assigned_to_user ?? <span className="text-amber-600">{translate("Unassigned")}</span>}</td>
                          <td className="py-2 text-right tabular-nums">{o.age_days}{translate(" d")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
