import { useCallback, useEffect, useState } from "react"
import { ChefHat, Check, RefreshCw, Clock } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

interface KotItem {
  name: string
  item_name: string
  qty: number
  instructions: string | null
  kot_status: string
}
interface KotOrder {
  name: string
  outlet_name: string
  room_no: string
  table_no: string | null
  creation: string
  notes: string | null
  items: KotItem[]
}

function minsAgo(iso: string): number {
  return Math.max(0, Math.round((Date.now() - new Date(iso.replace(" ", "T")).getTime()) / 60000))
}

export default function Kitchen() {
  const [station, setStation] = useState("")
  const [outlet, setOutlet] = useState("")
  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [orders, setOrders] = useState<KotOrder[]>([])
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    call<{ name: string; outlet_name: string }[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then(setOutlets).catch(() => {})
  }, [])

  const load = useCallback(() => {
    call<KotOrder[]>("kamra.pos.kitchen_queue", {
      property: getCurrentProperty(),
      outlet: outlet || null,
      station: station || null,
    }).then(setOrders).catch(() => {})
  }, [station, outlet])

  useEffect(() => {
    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [load])

  async function prepared(order: string, item?: string) {
    setBusy(order + (item ?? ""))
    try {
      await call("kamra.pos.mark_prepared", { order, item_row: item ?? null })
      load()
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
          <ChefHat className="size-5 text-brand-600" />Kitchen display
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"
            value={outlet} onChange={(e) => setOutlet(e.target.value)}>
            <option value="">All outlets</option>
            {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
          </select>
          <div className="flex rounded-lg border border-zinc-200 bg-white p-0.5 text-sm">
            {["", "Kitchen", "Bar"].map((s) => (
              <button key={s} onClick={() => setStation(s)}
                className={"rounded-md px-3 py-1.5 font-medium " +
                  (station === s ? "bg-brand-600 text-white" : "text-zinc-600")}>
                {s || "All"}
              </button>
            ))}
          </div>
          <button onClick={load} aria-label="Refresh"><RefreshCw className="size-5 text-zinc-400" /></button>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 p-12 text-center text-zinc-400">
          No open tickets. The kitchen is clear.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {orders.map((o) => {
            const age = minsAgo(o.creation)
            return (
              <div key={o.name}
                className={cn("flex flex-col rounded-2xl border-2 bg-white",
                  age >= 15 ? "border-rose-400" : age >= 8 ? "border-amber-400" : "border-zinc-200")}>
                <div className="flex items-center justify-between border-b border-zinc-100 px-3 py-2">
                  <span className="text-sm font-bold">
                    {o.room_no ? `Room ${o.room_no}` : o.table_no ? `Table ${o.table_no}` : o.outlet_name}
                  </span>
                  <span className={cn("inline-flex items-center gap-1 text-xs font-medium",
                    age >= 15 ? "text-rose-600" : age >= 8 ? "text-amber-600" : "text-zinc-400")}>
                    <Clock className="size-3" />{age}m
                  </span>
                </div>
                <ul className="flex-1 divide-y divide-zinc-50 px-3 py-1">
                  {o.items.map((it) => (
                    <li key={it.name} className="flex items-start gap-2 py-2">
                      <span className="w-7 shrink-0 text-center text-lg font-bold tabular-nums text-brand-700">{Math.round(it.qty)}</span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold">{it.item_name}</div>
                        {it.instructions && (
                          <div className="text-xs font-medium text-rose-600">! {it.instructions}</div>
                        )}
                      </div>
                      <button disabled={busy === o.name + it.name}
                        onClick={() => prepared(o.name, it.name)}
                        className="rounded-lg border border-zinc-300 p-1 text-zinc-400 hover:border-emerald-400 hover:text-emerald-600">
                        <Check className="size-4" />
                      </button>
                    </li>
                  ))}
                </ul>
                {o.notes && <div className="px-3 pb-1 text-xs text-zinc-500">Note: {o.notes}</div>}
                <div className="p-2">
                  <Button className="w-full" disabled={busy === o.name} onClick={() => prepared(o.name)}>
                    <Check className="size-4" />All ready
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
