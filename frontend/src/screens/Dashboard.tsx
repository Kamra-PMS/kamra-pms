import { useCallback, useEffect, useState } from "react"
import {
  BedDouble, LogIn, LogOut, Users, IndianRupee, Wallet,
  Building2, Sparkles, Brush, Receipt,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

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
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
          <Icon className="size-3.5" aria-hidden />
          {label}
        </div>
        <div className={`mt-1 text-2xl font-bold ${tone ?? "text-zinc-800"}`}>{value}</div>
        {sub && <div className="mt-0.5 text-xs text-zinc-400">{sub}</div>}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
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
      call<PropDash>("kamra.dashboards.property_dashboard", {
        property: getCurrentProperty(),
      }).then(setProp).catch((e) => setError(serverError(e)))
    } else {
      call<Portfolio>("kamra.dashboards.portfolio_dashboard", {})
        .then(setPort).catch((e) => setError(serverError(e)))
    }
  }, [scope])
  useEffect(load, [load])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-zinc-800">Dashboard</h1>
          <p className="text-xs text-zinc-500">
            {scope === "property"
              ? "Today at this property, by department."
              : "The whole portfolio at a glance."}
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
                {s === "property" ? "This property" : "All properties"}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {scope === "property" && prop && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Tile icon={BedDouble} label="Occupancy" value={`${prop.occupancy_pct}%`}
              sub={`${prop.total_rooms} rooms`} tone="text-brand-600" />
            <Tile icon={LogIn} label="Arrivals" value={String(prop.arrivals)} />
            <Tile icon={LogOut} label="Departures" value={String(prop.departures)} />
            <Tile icon={Users} label="In house" value={String(prop.in_house)} />
            <Tile icon={IndianRupee} label="Revenue" value={`₹${inr(prop.revenue_today)}`}
              sub="today" />
            <Tile icon={Wallet} label="Collections" value={`₹${inr(prop.collections_today)}`}
              sub="today" />
          </div>

          <Card>
            <CardHeader><CardTitle>Statistics (month to date)</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {[
                  ["Occupancy", `${prop.statistics.mtd_occupancy_pct}%`],
                  ["Revenue", `₹${inr(prop.statistics.mtd_revenue)}`],
                  ["ADR", `₹${inr(prop.statistics.adr)}`],
                  ["RevPAR", `₹${inr(prop.statistics.revpar)}`],
                  ["Rooms sold", inr(prop.statistics.rooms_sold_mtd)],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">{k}</div>
                    <div className="mt-0.5 text-lg font-semibold text-zinc-800">{v}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-1.5"><Sparkles className="size-4 text-brand-600" />Front desk</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <Row label="Arrivals" value={prop.arrivals} />
                <Row label="Departures" value={prop.departures} />
                <Row label="In house" value={prop.in_house} />
                <Row label="No-shows" value={prop.no_shows} tone={prop.no_shows ? "text-rose-600" : undefined} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-1.5"><Brush className="size-4 text-brand-600" />Housekeeping</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <Row label="Clean" value={prop.housekeeping.room_status.Clean ?? 0} />
                <Row label="Dirty" value={prop.housekeeping.room_status.Dirty ?? 0} tone={prop.housekeeping.room_status.Dirty ? "text-amber-600" : undefined} />
                <Row label="Inspected" value={prop.housekeeping.room_status.Inspected ?? 0} />
                <Row label="Out of order" value={prop.housekeeping.room_status["Out of Order"] ?? 0} />
                <Row label="Open tasks" value={prop.housekeeping.open_tasks} />
                <Row label="Overdue" value={prop.housekeeping.overdue_tasks} tone={prop.housekeeping.overdue_tasks ? "text-rose-600" : undefined} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-1.5"><Receipt className="size-4 text-brand-600" />Finance</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                <Row label="Collected today" value={`₹${inr(prop.finance.collections_today)}`} />
                <Row label="Outstanding" value={`₹${inr(prop.finance.outstanding)}`} tone={prop.finance.outstanding ? "text-amber-600" : undefined} />
                <Row label="Open folios" value={prop.finance.open_folios} />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {scope === "portfolio" && port && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Tile icon={Building2} label="Properties" value={String(port.totals.properties)}
              sub={`${port.totals.total_rooms} rooms`} />
            <Tile icon={BedDouble} label="Occupancy" value={`${port.totals.occupancy_pct}%`} tone="text-brand-600" />
            <Tile icon={LogIn} label="Arrivals" value={String(port.totals.arrivals)} />
            <Tile icon={Users} label="In house" value={String(port.totals.in_house)} />
            <Tile icon={IndianRupee} label="Revenue" value={`₹${inr(port.totals.revenue_today)}`} sub="today" />
            <Tile icon={Wallet} label="Collections" value={`₹${inr(port.totals.collections_today)}`} sub="today" />
          </div>

          <Card>
            <CardHeader><CardTitle>By property</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                      <th className="py-2 pr-3">Property</th>
                      <th className="py-2 pr-3 text-right">Occ %</th>
                      <th className="py-2 pr-3 text-right">Arr</th>
                      <th className="py-2 pr-3 text-right">Dep</th>
                      <th className="py-2 pr-3 text-right">In-house</th>
                      <th className="py-2 pr-3 text-right">Revenue</th>
                      <th className="py-2 pr-3 text-right">Collected</th>
                      <th className="py-2 text-right">Outstanding</th>
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
                        <td className="py-2 pr-3 text-right tabular-nums">₹{inr(p.revenue_today)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">₹{inr(p.collections_today)}</td>
                        <td className="py-2 text-right tabular-nums">₹{inr(p.outstanding)}</td>
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
  return (
    <div className="flex items-center justify-between">
      <span className="text-zinc-500">{label}</span>
      <span className={`font-semibold tabular-nums ${tone ?? "text-zinc-800"}`}>{String(value)}</span>
    </div>
  )
}
