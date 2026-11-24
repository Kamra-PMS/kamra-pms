/** F&B shift dashboard - the outlet's day at a glance: sales, covers, what's
 *  still open, the exceptions a manager signs off (NC, voids, cancellations),
 *  and how fast the kitchen is turning tickets. Read-only; auto-refreshes. */

import { useCallback, useEffect, useState } from "react"
import {
  UtensilsCrossed, Receipt, Users, Gift, Ban, ChefHat, Clock,
  Wallet, TrendingUp,
} from "lucide-react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { serverError } from "../lib/resource"
import { cur, moneyLocale } from "../lib/money"
import { cn } from "../lib/utils"
import { t as translate, useUILanguage } from "../lib/i18n"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

interface Bucket { label: string; bills: number; total: number }
interface OpenBill {
  name: string
  label: string
  status: string
  order_type: string | null
  order_total: number
  kot_no: number | null
  creation: string
}
interface Dash {
  outlet: string
  date: string
  gross_sales: number
  bills: number
  covers: number
  avg_bill: number
  by_order_type: Bucket[]
  by_tender: Bucket[]
  open_bills: OpenBill[]
  nc: {
    count: number
    value: number
    bills: { name: string; label: string; subtotal: number; authorized_by: string | null; note: string | null }[]
  }
  voids: { order: string; label: string; item_name: string; qty: number; amount: number; reason: string | null }[]
  cancellations: { name: string; label: string; order_total: number; reason: string | null }[]
  top_items: { item_name: string; qty: number; amount: number }[]
  avg_fire_to_ready_mins: number | null
}
interface Outlet { name: string; outlet_name: string }

function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

function ago(ts?: string) {
  if (!ts) return ""
  const mins = Math.max(0, Math.round((Date.now() - new Date(ts.replace(" ", "T")).getTime()) / 60000))
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function Kpi({ icon: Icon, label, value, sub, tone }: {
  icon: typeof Wallet
  label: string
  value: string
  sub?: string
  tone?: "amber" | "rose"
}) {
  useUILanguage()
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-zinc-400">
        <Icon className={cn("size-3.5",
          tone === "amber" ? "text-amber-500" : tone === "rose" ? "text-rose-500" : "text-brand-600")} />
        {translate(label)}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-zinc-900">{value}</div>
      {sub && <div className="text-xs text-zinc-400">{translate(sub)}</div>}
    </div>
  )
}

function BucketBars({ title, rows }: { title: string; rows: Bucket[] }) {
  useUILanguage()
  const max = Math.max(1, ...rows.map((r) => r.total))
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3">
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-zinc-500">{translate(title)}</h3>
      {rows.length === 0 && <p className="py-2 text-xs text-zinc-400">{translate("Nothing settled yet.")}</p>}
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.label}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium text-zinc-700">{translate(r.label)}</span>
              <span className="tabular-nums text-zinc-600">
                {cur()}{inr(r.total)} <span className="text-xs text-zinc-400">· {r.bills}{translate(" bill")}{r.bills === 1 ? "" : translate("s")}</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round((r.total / max) * 100)}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function PosDashboard() {
  useUILanguage()
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outlet, setOutlet] = useState("")
  const [date, setDate] = useState(today())
  const [toDate, setToDate] = useState("") // "" = the one day
  const [data, setData] = useState<Dash | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<Outlet[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then((o) => { setOutlets(o); if (o[0]) setOutlet(o[0].name) })
      .catch((e) => setError(serverError(e)))
  }, [])

  const load = useCallback(() => {
    if (!outlet) return
    call<Dash>("kamra.pos.outlet_dashboard", { outlet, date, to_date: toDate || undefined })
      .then((d) => { setData(d); setError(null) })
      .catch((e) => setError(serverError(e)))
  }, [outlet, date, toDate])

  useEffect(() => {
    load()
    if ((toDate || date) !== today()) return // the past doesn't move
    const unsub = subscribeRealtime(load)
    const t = setInterval(load, 30_000)
    return () => { unsub(); clearInterval(t) }
  }, [load, date, toDate])

  const inputCls =
    "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm " +
    "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
          <TrendingUp className="size-5 text-brand-600" />{translate("F&B Dashboard")}<select className={inputCls + " font-normal"} value={outlet} onChange={(e) => setOutlet(e.target.value)}>
            {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
          </select>
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" aria-label={translate("From")} className={inputCls} value={date} max={today()}
            onChange={(e) => setDate(e.target.value || today())} />
          <span className="text-sm text-zinc-400">→</span>
          <input type="date" aria-label={translate("To")} className={inputCls} value={toDate || date}
            min={date} max={today()}
            onChange={(e) => setToDate(e.target.value === date ? "" : e.target.value)} />
          <Link to="/pos"
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-50">
            <UtensilsCrossed className="size-4" />{translate("Open POS")}</Link>
        </div>
      </div>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(error)}</div>}

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Kpi icon={Wallet} label={translate("Gross sales")} value={`${cur()}${inr(data.gross_sales)}`}
              sub={translate("{v0} bill{v1} settled", { v0: String(data.bills), v1: String(data.bills === 1 ? "" : "s") })} />
            <Kpi icon={Receipt} label={translate("Avg bill")} value={`${cur()}${inr(data.avg_bill)}`} />
            <Kpi icon={Users} label={translate("Covers")} value={inr(data.covers)} />
            <Kpi icon={Clock} label={translate("Open bills")} value={String(data.open_bills.length)}
              sub={translate("{v0}{v1} unsettled", { v0: String(cur()), v1: String(inr(data.open_bills.reduce((s, b) => s + Number(b.order_total || 0), 0))) })} />
            <Kpi icon={Gift} label={translate("Complimentary")} value={String(data.nc.count)} tone="amber"
              sub={translate("{v0}{v1} given away", { v0: String(cur()), v1: String(inr(data.nc.value)) })} />
            <Kpi icon={ChefHat} label={translate("Fire → ready")}
              value={data.avg_fire_to_ready_mins === null ? "-" : `${data.avg_fire_to_ready_mins}m`}
              sub={translate("kitchen average")} />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <BucketBars title={translate("Sales by order type")} rows={data.by_order_type} />
            <BucketBars title={translate("Sales by tender")} rows={data.by_tender} />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {/* open bills */}
            <div className="rounded-xl border border-zinc-200 bg-white p-3">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-zinc-500">{translate("Open bills (")}{data.open_bills.length})
              </h3>
              {data.open_bills.length === 0 ? (
                <p className="py-2 text-xs text-zinc-400">{translate("Every bill is settled. Clean floor.")}</p>
              ) : (
                <ul className="divide-y divide-zinc-50">
                  {data.open_bills.map((b) => (
                    <li key={b.name} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{translate(b.label)}</span>
                        <span className="ml-1.5 text-xs text-zinc-400">
                          {b.order_type}{b.kot_no ? translate(" · KOT {v0}", { v0: String(b.kot_no) }) : ""} · {translate(b.status)}
                        </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 tabular-nums">
                        <span className="font-semibold">{cur()}{inr(b.order_total)}</span>
                        <span className={cn("rounded px-1 text-[10px] font-bold",
                          Date.now() - new Date(b.creation.replace(" ", "T")).getTime() > 90 * 60000
                            ? "bg-rose-50 text-rose-600" : "bg-zinc-100 text-zinc-500")}>
                          {ago(b.creation)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* top items */}
            <div className="rounded-xl border border-zinc-200 bg-white p-3">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-zinc-500">{translate("Top items")}</h3>
              {data.top_items.length === 0 ? (
                <p className="py-2 text-xs text-zinc-400">{translate("Nothing sold yet.")}</p>
              ) : (
                <ul className="divide-y divide-zinc-50">
                  {data.top_items.map((t, i) => (
                    <li key={t.item_name} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                      <span className="min-w-0 truncate">
                        <span className="mr-1.5 inline-block w-5 text-center text-xs font-bold text-zinc-300">{i + 1}</span>
                        <span className="font-medium text-zinc-700">{t.item_name}</span>
                      </span>
                      <span className="shrink-0 tabular-nums text-zinc-600">
                        {Math.round(t.qty)}× <span className="text-xs text-zinc-400">· {cur()}{inr(t.amount)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* exceptions - what a manager signs off */}
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="rounded-xl border border-amber-200 bg-white p-3">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-amber-700">
                <Gift className="size-3.5" />{translate("Complimentary (")}{data.nc.count} · {cur()}{inr(data.nc.value)})
              </h3>
              {data.nc.bills.length === 0 ? (
                <p className="py-2 text-xs text-zinc-400">{translate("No NC bills.")}</p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {data.nc.bills.map((b) => (
                    <li key={b.name} className="flex items-start justify-between gap-2">
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{translate(b.label)}</span>
                        <span className="block truncate text-xs text-zinc-400">{translate("auth: ")}{b.authorized_by}{b.note ? ` · ${b.note}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 tabular-nums text-zinc-600">{cur()}{inr(b.subtotal)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-rose-200 bg-white p-3">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-rose-700">
                <Ban className="size-3.5" />{translate("Voided lines (")}{data.voids.length})
              </h3>
              {data.voids.length === 0 ? (
                <p className="py-2 text-xs text-zinc-400">{translate("No voids.")}</p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {data.voids.map((v, i) => (
                    <li key={`${v.order}-${i}`} className="flex items-start justify-between gap-2">
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{Math.round(v.qty)}× {v.item_name}</span>
                        <span className="block truncate text-xs text-zinc-400">{translate(v.label)} · {v.reason || translate("no reason")}</span>
                      </span>
                      <span className="shrink-0 tabular-nums text-zinc-600">{cur()}{inr(v.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-rose-200 bg-white p-3">
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-rose-700">
                <Ban className="size-3.5" />{translate("Cancelled bills (")}{data.cancellations.length})
              </h3>
              {data.cancellations.length === 0 ? (
                <p className="py-2 text-xs text-zinc-400">{translate("No cancellations.")}</p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {data.cancellations.map((c) => (
                    <li key={c.name} className="flex items-start justify-between gap-2">
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{translate(c.label)}</span>
                        <span className="block truncate text-xs text-zinc-400">{c.reason || translate("no reason recorded")}</span>
                      </span>
                      <span className="shrink-0 tabular-nums text-zinc-600">{cur()}{inr(c.order_total)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}

      {!data && !error && (
        <div className="rounded-xl border border-dashed border-zinc-300 p-10 text-center text-sm text-zinc-400">{translate("Loading the day…")}</div>
      )}
    </div>
  )
}
