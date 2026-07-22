import { useCallback, useEffect, useState } from "react"
import { ChevronLeft, ChevronRight, Target } from "lucide-react"

import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cur, moneyLocale } from "../lib/money"

const inr = (n: number) =>
  Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

interface BvaRow {
  metric: string
  key: string
  actual: number
  target: number
  variance: number
  attainment: number | null
}
interface Bva {
  period: string
  days_elapsed: number
  total_days: number
  rows: BvaRow[]
  has_budget: boolean
}
interface Contrib {
  by: string
  total: number
  rows: { label: string; bookings: number; room_nights: number; revenue: number; share: number }[]
}

function shiftMonth(period: string, by: number) {
  const [y, m] = period.split("-").map(Number)
  const d = new Date(y, m - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}
const isPct = (k: string) => k === "occupancy_pct"
const fmt = (k: string, n: number) =>
  isPct(k) ? `${n}%` : `${cur()}${inr(n)}`

function attainTone(a: number | null) {
  if (a === null) return "text-zinc-400"
  if (a >= 100) return "text-emerald-600"
  if (a >= 80) return "text-amber-600"
  return "text-rose-600"
}

// ---------------------------------------------------------------------------

function BudgetVsActual() {
  const property = getCurrentProperty()
  const [period, setPeriod] = useState(() =>
    new Date().toISOString().slice(0, 7),
  )
  const [data, setData] = useState<Bva | null>(null)
  const [edit, setEdit] = useState(false)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Bva>("kamra.reports.budget_vs_actual", { property, period })
      .then((d) => {
        setData(d)
        const dr: Record<string, string> = {}
        for (const r of d.rows) dr[r.key] = r.target ? String(r.target) : ""
        setDraft(dr)
      })
      .catch((e) => setError(serverError(e)))
  }, [property, period])
  useEffect(load, [load])

  const save = () =>
    act(() =>
      call("kamra.reports.save_budget", {
        property,
        period,
        room_revenue_target: Number(draft.room_revenue) || 0,
        occupancy_target: Number(draft.occupancy_pct) || 0,
        adr_target: Number(draft.adr) || 0,
        revpar_target: Number(draft.revpar) || 0,
      }).then(() => setEdit(false)),
    )

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <Target className="size-4 text-brand-600" aria-hidden />
            Budget vs Actual
          </CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Month-to-date performance against your targets.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" onClick={() => setPeriod((p) => shiftMonth(p, -1))}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="min-w-20 text-center text-sm font-medium">{period}</span>
          <Button variant="outline" onClick={() => setPeriod((p) => shiftMonth(p, 1))}>
            <ChevronRight className="size-4" />
          </Button>
          <Button variant="outline" onClick={() => setEdit((e) => !e)}>
            {edit ? "Cancel" : data?.has_budget ? "Edit targets" : "Set targets"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        {data && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                <th className="py-2 pr-3">Metric</th>
                <th className="py-2 pr-3 text-right">Actual (MTD)</th>
                <th className="py-2 pr-3 text-right">Target</th>
                <th className="py-2 pr-3 text-right">Variance</th>
                <th className="py-2 text-right">Attainment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {data.rows.map((r) => (
                <tr key={r.key}>
                  <td className="py-2.5 pr-3 font-medium">{r.metric}</td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {fmt(r.key, r.actual)}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {edit ? (
                      <input
                        type="number"
                        className="w-24 rounded-lg border border-zinc-300 px-2 py-1 text-right text-sm"
                        value={draft[r.key] ?? ""}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [r.key]: e.target.value }))
                        }
                      />
                    ) : r.target ? (
                      fmt(r.key, r.target)
                    ) : (
                      <span className="text-zinc-300">-</span>
                    )}
                  </td>
                  <td
                    className={
                      "py-2.5 pr-3 text-right tabular-nums " +
                      (r.variance >= 0 ? "text-emerald-600" : "text-rose-600")
                    }
                  >
                    {r.target
                      ? (r.variance >= 0 ? "+" : "") + fmt(r.key, r.variance)
                      : "-"}
                  </td>
                  <td className="py-2.5 text-right">
                    {r.attainment !== null ? (
                      <span
                        className={
                          "font-semibold tabular-nums " +
                          attainTone(r.attainment)
                        }
                      >
                        {r.attainment}%
                      </span>
                    ) : (
                      <span className="text-zinc-300">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {edit && (
          <div className="mt-3 flex justify-end">
            <Button disabled={busy} onClick={save}>
              {busy ? "Saving..." : "Save targets"}
            </Button>
          </div>
        )}
        {data && !data.has_budget && !edit && (
          <p className="mt-3 text-xs text-zinc-400">
            No targets set for {data.period} yet - "Set targets" to track
            attainment.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------

const BY_OPTIONS: { key: string; label: string }[] = [
  { key: "source", label: "By source" },
  { key: "company", label: "By company" },
  { key: "travel_agent", label: "By travel agent" },
]

function Contribution() {
  const property = getCurrentProperty()
  const today = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10)
  const [from, setFrom] = useState(monthAgo)
  const [to, setTo] = useState(today)
  const [by, setBy] = useState("source")
  const [data, setData] = useState<Contrib | null>(null)

  const load = useCallback(() => {
    call<Contrib>("kamra.reports.contribution", {
      property,
      from_date: from,
      to_date: to,
      by,
    }).then(setData)
  }, [property, from, to, by])
  useEffect(load, [load])

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Contribution analysis</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Who brings the business - revenue and share by channel.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <input
            type="date"
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            aria-label="From"
          />
          <span className="text-xs text-zinc-400">to</span>
          <input
            type="date"
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            aria-label="To"
          />
          <select
            className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm"
            value={by}
            onChange={(e) => setBy(e.target.value)}
            aria-label="Group by"
          >
            {BY_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent>
        {data && data.rows.length === 0 && (
          <p className="py-6 text-center text-sm text-zinc-400">
            No bookings in this window.
          </p>
        )}
        {data && data.rows.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                <th className="py-2 pr-3">{BY_OPTIONS.find((o) => o.key === by)?.label.replace("By ", "")}</th>
                <th className="py-2 pr-3 text-right">Bookings</th>
                <th className="py-2 pr-3 text-right">Room nights</th>
                <th className="py-2 pr-3 text-right">Revenue {cur()}</th>
                <th className="py-2 text-right">Share</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {data.rows.map((r) => (
                <tr key={r.label}>
                  <td className="py-2.5 pr-3 font-medium">{r.label}</td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">{r.bookings}</td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">{r.room_nights}</td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">{inr(r.revenue)}</td>
                  <td className="py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-100">
                        <div
                          className="h-full rounded-full bg-brand-500"
                          style={{ width: `${r.share}%` }}
                        />
                      </div>
                      <span className="w-10 text-right tabular-nums">{r.share}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-zinc-200 font-semibold">
                <td className="py-2 pr-3">Total</td>
                <td />
                <td />
                <td className="py-2 pr-3 text-right tabular-nums">{inr(data.total)}</td>
                <td className="py-2 text-right">100%</td>
              </tr>
            </tfoot>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

export default function RevenueReports() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">
          Revenue Reports
        </h1>
        <p className="mt-0.5 text-sm text-zinc-500">
          Targets vs performance, and where the business comes from.
        </p>
      </header>
      <BudgetVsActual />
      <Contribution />
    </div>
  )
}
