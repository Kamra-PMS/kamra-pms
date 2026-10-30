import { useCallback, useEffect, useState } from "react"
import { useRealtime } from "../lib/realtime"
import {
  BedDouble, LogIn, Users, Banknote, Wallet, Building2, Brush, Receipt,
  PieChart, TrendingUp, BarChart3,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { StatCard } from "../components/ui/stat-card"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate, useUILanguage } from "../lib/i18n"


const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

interface PropDash {
  property_name: string
  date: string
  total_rooms: number
  occupancy_pct: number
  arrivals: number
  departures: number
  in_house: number
  no_shows: number
  revenue_today: number
  collections_today: number
  statistics: {
    mtd_occupancy_pct: number
    mtd_revenue: number
    adr: number
    revpar: number
    rooms_sold_mtd: number
  }
  housekeeping: {
    room_status: Record<string, number>
    occupied: number
    vacant: number
    open_tasks: number
    overdue_tasks: number
  }
  finance: {
    collections_today: number
    outstanding: number
    open_folios: number
  }
  comparison?: {
    financial_year_start: string
    periods: Period[]
  }
}

type Metric = "occupancy_pct" | "rooms_sold" | "room_revenue" | "total_revenue" | "adr" | "revpar"
interface Period {
  id: "today" | "mtd" | "ytd" | "on_the_books"
  from_date: string
  to_date: string
  ly_from_date: string
  ly_to_date: string
  this_year: Partial<Record<Metric, number>>
  last_year: Partial<Record<Metric, number>>
  change_pct: Partial<Record<Metric, number | null>>
}

interface Portfolio {
  date: string
  totals: {
    properties: number
    total_rooms: number
    occupancy_pct: number
    arrivals: number
    departures: number
    in_house: number
    revenue_today: number
    collections_today: number
    outstanding: number
  }
  properties: {
    property: string
    property_name: string
    total_rooms: number
    occupancy_pct: number
    arrivals: number
    departures: number
    in_house: number
    revenue_today: number
    collections_today: number
    outstanding: number
  }[]
}

function Tile({ icon: Icon, label, value, sub, tone }: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  useUILanguage()
  return (
    <StatCard
      icon={<Icon className="size-4" />}
      label={translate(label)}
      value={value}
      sub={translate(sub)}
      accent={tone === "text-brand-600"}
    />
  )
}

export default function Dashboard() {
  const { t } = useT()
  const [scope, setScope] = useState<"property" | "portfolio">("property")
  const [multi, setMulti] = useState(false)
  const [prop, setProp] = useState<PropDash | null>(null)
  const [port, setPort] = useState<Portfolio | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<{ name: string }[]>("kamra.api.my_properties")
      .then((p) => setMulti((p?.length ?? 0) > 1))
      .catch(() => setMulti(false))
  }, [])

  const load = useCallback(() => {
    setError(null)
    if (scope === "property") {
      call<PropDash & { figures_hidden?: boolean }>("kamra.dashboards.property_dashboard", {
        property: getCurrentProperty(),
        with_comparison: 1,
      }).then((d) => d.figures_hidden
        ? setError(t("The revenue dashboard is for Finance, Revenue and managers."))
        : setProp(d)).catch((e) => setError(serverError(e)))
    } else {
      call<Portfolio>("kamra.dashboards.portfolio_dashboard", {})
        .then(setPort).catch((e) => setError(serverError(e)))
    }
  }, [scope, t])
  useEffect(load, [load])
  useRealtime(load)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">{t("Revenue Dashboard")}</h1>
          <p className="text-xs text-zinc-500">
            {scope === "property"
              ? t("Today at this property, by department.")
              : t("The whole portfolio at a glance.")}
          </p>
        </div>
        {multi && (
          <div className="flex rounded-lg border border-zinc-200 bg-white p-0.5 text-sm">
            {(["property", "portfolio"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={
                  "rounded-md px-3 py-1.5 font-medium " +
                  (scope === s ? "bg-brand-600 text-white" : "text-zinc-600")
                }
              >
                {s === "property" ? t("This property") : t("All properties")}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      {scope === "property" && prop && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Tile icon={PieChart} label={t("Occupancy")} value={`${prop.occupancy_pct}%`}
              sub={t("{n} rooms", { n: prop.total_rooms })} tone="text-brand-600" />
            <Tile icon={TrendingUp} label={t("ADR")} value={`${cur()}${inr(prop.statistics.adr)}`}
              sub={t("month to date")} />
            <Tile icon={BarChart3} label={t("RevPAR")} value={`${cur()}${inr(prop.statistics.revpar)}`}
              sub={t("month to date")} />
            <Tile icon={Banknote} label={t("Revenue")} value={`${cur()}${inr(prop.revenue_today)}`}
              sub={t("today")} />
            <Tile icon={Wallet} label={t("Collections")} value={`${cur()}${inr(prop.collections_today)}`}
              sub={t("today")} />
            <Tile icon={Receipt} label={t("Outstanding")} value={`${cur()}${inr(prop.finance.outstanding)}`}
              sub={t("receivable")} />
          </div>

          <Card>
            <CardHeader><CardTitle>{t("Statistics (month to date)")}</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {[
                  [t("Occupancy"), `${prop.statistics.mtd_occupancy_pct}%`],
                  [t("Revenue"), `${cur()}${inr(prop.statistics.mtd_revenue)}`],
                  [t("ADR"), `${cur()}${inr(prop.statistics.adr)}`],
                  [t("RevPAR"), `${cur()}${inr(prop.statistics.revpar)}`],
                  [t("Rooms sold"), inr(prop.statistics.rooms_sold_mtd)],
                ].map(([k, v]) => (
                  <div key={String(k)}>
                    <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">{translate(k)}</div>
                    <div className="mt-0.5 text-lg font-semibold text-zinc-800">{v}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {prop.comparison && <Comparison data={prop.comparison} />}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-1.5"><Brush className="size-4 text-brand-600" />{t("Housekeeping")}</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <Row label={t("Clean")} value={prop.housekeeping.room_status.Clean ?? 0} />
                <Row label={t("Dirty")} value={prop.housekeeping.room_status.Dirty ?? 0} tone={prop.housekeeping.room_status.Dirty ? "text-amber-600" : undefined} />
                <Row label={t("Inspected")} value={prop.housekeeping.room_status.Inspected ?? 0} />
                <Row label={t("Out of order")} value={prop.housekeeping.room_status["Out of Order"] ?? 0} />
                <Row label={t("Open tasks")} value={prop.housekeeping.open_tasks} />
                <Row label={t("Overdue")} value={prop.housekeeping.overdue_tasks} tone={prop.housekeeping.overdue_tasks ? "text-rose-600" : undefined} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-1.5"><Receipt className="size-4 text-brand-600" />{t("Finance")}</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <Row label={t("Collected today")} value={`${cur()}${inr(prop.finance.collections_today)}`} />
                <Row label={t("Outstanding")} value={`${cur()}${inr(prop.finance.outstanding)}`} tone={prop.finance.outstanding ? "text-amber-600" : undefined} />
                <Row label={t("Open folios")} value={prop.finance.open_folios} />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {scope === "portfolio" && port && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Tile icon={Building2} label={t("Properties")} value={String(port.totals.properties)}
              sub={t("{n} rooms", { n: port.totals.total_rooms })} />
            <Tile icon={BedDouble} label={t("Occupancy")} value={`${port.totals.occupancy_pct}%`} tone="text-brand-600" />
            <Tile icon={LogIn} label={t("Arrivals")} value={String(port.totals.arrivals)} />
            <Tile icon={Users} label={t("In house")} value={String(port.totals.in_house)} />
            <Tile icon={Banknote} label={t("Revenue")} value={`${cur()}${inr(port.totals.revenue_today)}`} sub={t("today")} />
            <Tile icon={Wallet} label={t("Collections")} value={`${cur()}${inr(port.totals.collections_today)}`} sub={t("today")} />
          </div>

          <Card>
            <CardHeader><CardTitle>{t("By property")}</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                      <th className="py-2 pr-3">{t("Property")}</th>
                      <th className="py-2 pr-3 text-right">{t("Occ %")}</th>
                      <th className="py-2 pr-3 text-right">{t("Arr")}</th>
                      <th className="py-2 pr-3 text-right">{t("Dep")}</th>
                      <th className="py-2 pr-3 text-right">{t("In-house")}</th>
                      <th className="py-2 pr-3 text-right">{t("Revenue")}</th>
                      <th className="py-2 pr-3 text-right">{t("Collected")}</th>
                      <th className="py-2 text-right">{t("Outstanding")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {port.properties.map((p) => (
                      <tr key={p.property}>
                        <td className="py-2 pr-3 font-medium">{p.property_name}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{p.occupancy_pct}%</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{p.arrivals}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{p.departures}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{p.in_house}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{cur()}{inr(p.revenue_today)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{cur()}{inr(p.collections_today)}</td>
                        <td className="py-2 text-right tabular-nums">{cur()}{inr(p.outstanding)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  useUILanguage()
  return (
    <div className="flex items-center justify-between">
      <span className="text-zinc-500">{translate(label)}</span>
      <span className={`font-semibold tabular-nums ${tone ?? "text-zinc-800"}`}>{String(value)}</span>
    </div>
  )
}

const METRICS: [Metric, "pct" | "count" | "money"][] = [
  ["occupancy_pct", "pct"],
  ["rooms_sold", "count"],
  ["room_revenue", "money"],
  ["total_revenue", "money"],
  ["adr", "money"],
  ["revpar", "money"],
]

/** This year against the same dates last year: today, month to date, year
 * to date (from the country's financial year) and the next 90 days on the
 * books against what last year sold. kamra.dashboards.comparison */
function Comparison({ data }: { data: NonNullable<PropDash["comparison"]> }) {
  const { t } = useT()
  const [pid, setPid] = useState<Period["id"]>("mtd")
  const p = data.periods.find((x) => x.id === pid) ?? data.periods[0]
  if (!p) return null
  const periodLabel: Record<Period["id"], string> = {
    today: t("Today"),
    mtd: t("Month to date"),
    ytd: t("Year to date"),
    on_the_books: t("Next 90 days"),
  }
  const metricLabel: Record<Metric, string> = {
    occupancy_pct: t("Occupancy"),
    rooms_sold: t("Rooms sold"),
    room_revenue: t("Room revenue"),
    total_revenue: t("Total revenue"),
    adr: t("ADR"),
    revpar: t("RevPAR"),
  }
  const show = (v: number | undefined, kind: string) =>
    v == null ? "" : kind === "pct" ? `${v}%` : kind === "money" ? `${cur()}${inr(v)}` : inr(v)
  const range = (a: string, b: string) => (a === b ? a : t("{from} to {to}", { from: a, to: b }))
  return (
    <Card>
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{t("This year against last year")}</CardTitle>
        <div className="flex flex-wrap rounded-lg border border-zinc-200 bg-white p-0.5 text-xs">
          {data.periods.map((x) => (
            <button
              key={x.id}
              onClick={() => setPid(x.id)}
              aria-pressed={x.id === p.id}
              className={
                "rounded-md px-2.5 py-1 font-medium " +
                (x.id === p.id ? "bg-brand-600 text-white" : "text-zinc-600")
              }
            >
              {periodLabel[x.id]}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-xs font-medium text-zinc-500">
                <th className="py-2 pe-3 text-start" />
                <th className="py-2 pe-3 text-end" title={range(p.from_date, p.to_date)}>
                  {p.id === "on_the_books" ? t("On the books") : t("This year")}
                </th>
                <th className="py-2 pe-3 text-end" title={range(p.ly_from_date, p.ly_to_date)}>
                  {t("Last year")}
                </th>
                <th className="py-2 text-end">{t("Change %")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {METRICS.filter(([m]) => p.this_year[m] != null).map(([m, kind]) => {
                const ch = p.change_pct[m]
                return (
                  <tr key={m}>
                    <td className="py-1.5 pe-3 text-zinc-600">{metricLabel[m]}</td>
                    <td className="py-1.5 pe-3 text-end font-semibold tabular-nums text-zinc-900">
                      {show(p.this_year[m], kind)}
                    </td>
                    <td className="py-1.5 pe-3 text-end tabular-nums text-zinc-500">
                      {show(p.last_year[m], kind)}
                    </td>
                    <td
                      className={
                        "py-1.5 text-end tabular-nums " +
                        (ch == null || ch === 0
                          ? "text-zinc-400"
                          : ch > 0
                            ? "text-emerald-700"
                            : "text-rose-700")
                      }
                    >
                      {ch == null ? t("n/a") : `${ch > 0 ? "▲ +" : ch < 0 ? "▼ " : ""}${ch}%`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-zinc-400">
          {t("{this} against {last}. Year to date starts {fy}.", {
            this: range(p.from_date, p.to_date),
            last: range(p.ly_from_date, p.ly_to_date),
            fy: data.financial_year_start,
          })}
        </p>
      </CardContent>
    </Card>
  )
}
