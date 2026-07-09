import { useCallback, useEffect, useState } from "react"
import { AlarmClock } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
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
  category: string
  priority: string
  overdue_hours: number
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
}

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function humanMins(m: number | null): string {
  if (m == null) return "—"
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
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-400">No tickets.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="py-2 pr-3">{title.includes("category") ? "Category" : "Priority"}</th>
                  <th className="py-2 pr-3 text-right">Tickets</th>
                  <th className="py-2 pr-3 text-right">Resolved</th>
                  <th className="py-2 pr-3 text-right">Breached</th>
                  <th className="py-2 pr-3 text-right">Breach %</th>
                  <th className="py-2 text-right">Avg resolve</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map((r) => (
                  <tr key={r.label}>
                    <td className="py-2 pr-3 font-medium">{r.label}</td>
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
            <AlarmClock className="size-5 text-brand-600" />
            Operations SLA
          </h1>
          <p className="text-xs text-zinc-500">
            Are guest requests being resolved inside their promised window?
          </p>
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
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Tickets", String(data.total), "text-zinc-800"],
              ["Resolved", `${data.resolved} / ${data.total}`, "text-zinc-800"],
              [
                "Breach rate",
                `${data.breach_pct}%`,
                data.breach_pct >= 25 ? "text-rose-600" : data.breach_pct >= 10 ? "text-amber-600" : "text-brand-600",
              ],
              ["Avg resolve", humanMins(data.avg_resolve_mins), "text-zinc-800"],
            ].map(([label, val, tone]) => (
              <Card key={label}>
                <CardContent className="p-4">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                    {label}
                  </div>
                  <div className={`mt-1 text-2xl font-bold ${tone}`}>{val}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <GroupTable title="By category" rows={data.by_category} />
            <GroupTable title="By priority" rows={data.by_priority} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>
                Overdue now
                {data.overdue.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-rose-600">
                    {data.overdue.length} past due
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.overdue.length === 0 ? (
                <p className="py-6 text-center text-sm text-zinc-400">
                  Nothing overdue — every open request is inside its window.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                        <th className="py-2 pr-3">Ticket</th>
                        <th className="py-2 pr-3">Category</th>
                        <th className="py-2 pr-3">Priority</th>
                        <th className="py-2 text-right">Overdue by</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {data.overdue.map((o) => (
                        <tr key={o.name}>
                          <td className="py-2 pr-3 font-mono text-xs">{o.name}</td>
                          <td className="py-2 pr-3">{o.category}</td>
                          <td className="py-2 pr-3">{o.priority}</td>
                          <td className="py-2 text-right tabular-nums text-rose-600">
                            {o.overdue_hours} h
                          </td>
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
