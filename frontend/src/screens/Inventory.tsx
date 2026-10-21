import { useCallback, useEffect, useMemo, useState } from "react"
import {
  PackageSearch, RefreshCw, TriangleAlert, X, Truck, ClipboardCheck,
  Trash2, History, Ban,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

/* Kitchen stock. Two things here are deliberate and read as bugs if you don't
   know why:
    - Stock is PER OUTLET, so there is no merged "all outlets" total and this
       screen never offers one. There is no such number.
    - NEGATIVE is a valid state, not an error. It means the count is stale,
       and it is the loudest thing on the screen because it is the system
       admitting it doesn't know something. */

type Status = "OK" | "LOW" | "OUT" | "NEGATIVE"

interface StockRow {
  name: string
  ingredient: string
  ingredient_name: string
  uom: string
  category: string | null
  cost_per_unit: number | null
  qty_on_hand: number
  par_level: number
  last_counted_at: string | null
  status: Status
}
interface LedgerRow {
  name: string
  creation: string
  qty_change: number
  balance_after: number
  reason: string
  reference_doctype: string | null
  reference_name: string | null
  note: string | null
  supplier: string | null
}
interface LowRow {
  ingredient: string
  ingredient_name: string
  uom: string
  qty_on_hand: number
  status: Status
  dishes: { name: string; item_name: string; available: 0 | 1 }[]
}

const WRITE_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
const STATUSES: Status[] = ["NEGATIVE", "OUT", "LOW", "OK"]

const TONE: Record<Status, string> = {
  NEGATIVE: "bg-rose-100 text-rose-700 ring-1 ring-rose-300",
  OUT: "bg-zinc-200 text-zinc-700",
  LOW: "bg-amber-100 text-amber-700",
  OK: "bg-emerald-50 text-emerald-700",
}

function daysSince(iso: string | null): string | null {
  if (!iso) return null
  const d = Math.floor((Date.now() - new Date(iso.replace(" ", "T")).getTime()) / 86_400_000)
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d}d ago`
}
const fmt = (n: number) => (Math.round(n * 1000) / 1000).toString()

function StatusChip({ s }: { s: Status }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide", TONE[s])}>
      {s === "NEGATIVE" && <TriangleAlert className="size-3" />}{s}
    </span>
  )
}

function Modal({ title, onClose, children }: {
  title: string; onClose: () => void; children: React.ReactNode
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 p-4">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <h2 className="text-lg font-bold text-zinc-800">{title}</h2>
          <button onClick={onClose} aria-label="Close"
            className="grid size-9 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  )
}

export default function Inventory() {
  const { roles } = useAuth()
  const canWrite = roles.some((r) => WRITE_ROLES.includes(r))

  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [outlet, setOutlet] = useState("")
  const [rows, setRows] = useState<StockRow[]>([])
  const [low, setLow] = useState<LowRow[]>([])
  const [filter, setFilter] = useState<Status | "">("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [modal, setModal] = useState<"receive" | "count" | "waste" | null>(null)
  const [ledgerOf, setLedgerOf] = useState<StockRow | null>(null)

  useEffect(() => {
    call<{ name: string; outlet_name: string }[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then((o) => { setOutlets(o); if (o.length && !outlet) setOutlet(o[0].name) })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = useCallback(() => {
    if (!outlet) return
    const property = getCurrentProperty()
    call<StockRow[]>("kamra.inventory.stock_list", { property, outlet })
      .then(setRows).catch((e) => setErr(String(e)))
    call<LowRow[]>("kamra.inventory.low_stock", { property, outlet })
      .then(setLow).catch(() => {})
  }, [outlet])

  useEffect(() => { load() }, [load])

  const act = useCallback(async (method: string, params: Record<string, unknown>) => {
    setBusy(true); setErr(null)
    try {
      await call(`kamra.inventory.${method}`, { property: getCurrentProperty(), outlet, ...params })
      setModal(null)
      load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [outlet, load])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const r of rows) c[r.status] = (c[r.status] ?? 0) + 1
    return c
  }, [rows])

  const shown = filter ? rows.filter((r) => r.status === filter) : rows

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
          <PackageSearch className="size-5 text-brand-600" />Kitchen inventory
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          {/* Stock is per outlet. There is no "all outlets" option because
              there is no such quantity - the bar's limes are not the
              kitchen's limes. */}
          <select className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"
            value={outlet} onChange={(e) => setOutlet(e.target.value)}>
            {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
          </select>
          {canWrite && (
            <>
              <Button variant="outline" onClick={() => setModal("receive")}>
                <Truck className="size-4" />Receive
              </Button>
              <Button variant="outline" onClick={() => setModal("count")}>
                <ClipboardCheck className="size-4" />Stock take
              </Button>
              <Button variant="outline" onClick={() => setModal("waste")}>
                <Trash2 className="size-4" />Wastage
              </Button>
            </>
          )}
          <button onClick={load} aria-label="Refresh"><RefreshCw className="size-5 text-zinc-400" /></button>
        </div>
      </div>

      {err && (
        <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">
          {err}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {(["", ...STATUSES] as const).map((s) => (
          <button key={s || "all"} onClick={() => setFilter(s as Status | "")}
            className={cn("rounded-lg px-3 py-1.5 text-sm font-medium",
              filter === s ? "bg-brand-600 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
            {s || "All"}{s ? ` · ${counts[s] ?? 0}` : ` · ${rows.length}`}
          </button>
        ))}
      </div>

      {/* What's out, and the dishes it takes down with it. The system flags
          and offers; a human decides. Nothing is ever auto-86'd. */}
      {low.length > 0 && (
        <div className="rounded-2xl border-2 border-amber-300 bg-amber-50/50 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-black uppercase tracking-wide text-amber-800">
            <TriangleAlert className="size-4" />Needs attention · {low.length}
          </div>
          <ul className="space-y-2">
            {low.map((l) => (
              <li key={l.ingredient} className="flex flex-wrap items-center gap-2 text-sm">
                <StatusChip s={l.status} />
                <span className="font-bold text-zinc-800">{l.ingredient_name}</span>
                <span className="tabular-nums text-zinc-500">{fmt(l.qty_on_hand)} {l.uom}</span>
                {l.dishes.length > 0 && (
                  <span className="text-zinc-500">
                    → {l.dishes.filter((d) => d.available).map((d) => d.item_name).join(", ") || "no live dishes"}
                  </span>
                )}
                {canWrite && l.dishes.filter((d) => d.available).map((d) => (
                  <Button key={d.name} variant="outline"
                    className="h-8 border-amber-400 px-2 text-xs text-amber-800"
                    onClick={async () => {
                      await call("kamra.inventory.set_menu_availability", {
                        menu_item: d.name, available: 0,
                      })
                      load()
                    }}>
                    <Ban className="size-3" />86 {d.item_name}
                  </Button>
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}

      {shown.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 p-12 text-center text-zinc-400">
          {rows.length === 0
            ? "No ingredients stocked at this outlet yet. Add them under Ingredients, then Receive here."
            : "Nothing in this state."}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-bold">Ingredient</th>
                <th className="px-4 py-2 font-bold">Category</th>
                <th className="px-4 py-2 text-right font-bold">On hand</th>
                <th className="px-4 py-2 text-right font-bold">Par</th>
                <th className="px-4 py-2 font-bold">Status</th>
                <th className="px-4 py-2 font-bold">Counted</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {shown.map((r) => (
                <tr key={r.name} className={cn(r.status === "NEGATIVE" && "bg-rose-50/60")}>
                  <td className="px-4 py-2 font-semibold text-zinc-800">{r.ingredient_name}</td>
                  <td className="px-4 py-2 text-zinc-500">{r.category || "-"}</td>
                  <td className={cn("px-4 py-2 text-right font-bold tabular-nums",
                    r.status === "NEGATIVE" ? "text-rose-600" : "text-zinc-800")}>
                    {fmt(r.qty_on_hand)} <span className="font-normal text-zinc-400">{r.uom}</span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-zinc-400">
                    {r.par_level ? fmt(r.par_level) : "-"}
                  </td>
                  <td className="px-4 py-2"><StatusChip s={r.status} /></td>
                  <td className="px-4 py-2 text-zinc-400">
                    {r.status === "NEGATIVE"
                      ? <span className="font-bold text-rose-600">recount{daysSince(r.last_counted_at) ? ` · last ${daysSince(r.last_counted_at)}` : " · never counted"}</span>
                      : daysSince(r.last_counted_at) ?? "never"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button variant="ghost" className="h-8 px-2 text-xs"
                      onClick={() => setLedgerOf(r)}>
                      <History className="size-3.5" />Ledger
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal === "receive" && (
        <ReceiveModal rows={rows} outlet={outlet} busy={busy}
          onClose={() => setModal(null)} onSubmit={(p) => act("receive_stock", p)} />
      )}
      {modal === "count" && (
        <CountModal rows={rows} busy={busy}
          onClose={() => setModal(null)} onSubmit={(p) => act("adjust_stock", p)} />
      )}
      {modal === "waste" && (
        <WasteModal rows={rows} busy={busy}
          onClose={() => setModal(null)} onSubmit={(p) => act("record_wastage", p)} />
      )}
      {ledgerOf && (
        <LedgerModal row={ledgerOf} outlet={outlet} onClose={() => setLedgerOf(null)} />
      )}
    </div>
  )
}

function ReceiveModal({ rows, busy, onClose, onSubmit }: {
  rows: StockRow[]; outlet: string; busy: boolean; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [cost, setCost] = useState<Record<string, string>>({})
  const [supplier, setSupplier] = useState("")
  const [invoice, setInvoice] = useState("")
  const lines = Object.entries(picked)
    .filter(([, q]) => Number(q) > 0)
    .map(([ingredient, q]) => ({
      ingredient, qty: Number(q),
      ...(cost[ingredient] ? { cost_per_unit: Number(cost[ingredient]) } : {}),
    }))
  return (
    <Modal title="Receive stock" onClose={onClose}>
      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <input className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          placeholder="Supplier" value={supplier} onChange={(e) => setSupplier(e.target.value)} />
        <input className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          placeholder="Invoice no" value={invoice} onChange={(e) => setInvoice(e.target.value)} />
      </div>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-zinc-400">
          <tr><th className="pb-1">Ingredient</th><th className="pb-1">Qty in</th><th className="pb-1">Cost/unit</th></tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((r) => (
            <tr key={r.name}>
              <td className="py-1.5 font-medium">{r.ingredient_name}
                <span className="ml-1 text-xs text-zinc-400">{r.uom}</span></td>
              <td className="py-1.5"><input type="number" min="0" step="any" inputMode="decimal"
                className="w-24 rounded border border-zinc-300 px-2 py-1 tabular-nums"
                value={picked[r.ingredient] ?? ""}
                onChange={(e) => setPicked({ ...picked, [r.ingredient]: e.target.value })} /></td>
              <td className="py-1.5"><input type="number" min="0" step="any" inputMode="decimal"
                className="w-24 rounded border border-zinc-300 px-2 py-1 tabular-nums"
                placeholder={r.cost_per_unit ? String(r.cost_per_unit) : "-"}
                value={cost[r.ingredient] ?? ""}
                onChange={(e) => setCost({ ...cost, [r.ingredient]: e.target.value })} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-zinc-400">
        A cost here updates the ingredient's cost, which is what wastage gets valued at. Indicative only - it doesn't tie to the books.
      </p>
      <Button className="mt-4 h-12 w-full justify-center" disabled={busy || !lines.length}
        onClick={() => onSubmit({ rows: lines, supplier: supplier || null, invoice_no: invoice || null })}>
        Receive {lines.length || ""} ingredient{lines.length === 1 ? "" : "s"}
      </Button>
    </Modal>
  )
}

function CountModal({ rows, busy, onClose, onSubmit }: {
  rows: StockRow[]; busy: boolean; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  const [counted, setCounted] = useState<Record<string, string>>({})
  const [note, setNote] = useState("")
  const lines = Object.entries(counted)
    .filter(([, v]) => v !== "")
    .map(([ingredient, v]) => ({ ingredient, counted_qty: Number(v) }))
  return (
    <Modal title="Stock take" onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">
        Count what's physically on the shelf. Leave a row blank to skip it.
      </p>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-zinc-400">
          <tr><th className="pb-1">Ingredient</th><th className="pb-1 text-right">System</th>
            <th className="pb-1">Counted</th><th className="pb-1 text-right">Variance</th></tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((r) => {
            const v = counted[r.ingredient]
            const delta = v === "" || v === undefined ? null : Number(v) - r.qty_on_hand
            return (
              <tr key={r.name}>
                <td className="py-1.5 font-medium">{r.ingredient_name}
                  <span className="ml-1 text-xs text-zinc-400">{r.uom}</span></td>
                <td className="py-1.5 text-right tabular-nums text-zinc-400">{fmt(r.qty_on_hand)}</td>
                <td className="py-1.5">
                  {/* Deliberately blank, never pre-filled with the system qty:
                      pre-filling invites blind confirmation, which is exactly
                      how a count rots into fiction. */}
                  <input type="number" step="any" inputMode="decimal" placeholder="count…"
                    className="w-24 rounded border border-zinc-300 px-2 py-1 tabular-nums"
                    value={v ?? ""}
                    onChange={(e) => setCounted({ ...counted, [r.ingredient]: e.target.value })} />
                </td>
                <td className={cn("py-1.5 text-right font-bold tabular-nums",
                  delta === null ? "text-zinc-300"
                    : Math.abs(delta) < 1e-9 ? "text-zinc-400"
                      : delta < 0 ? "text-rose-600" : "text-emerald-600")}>
                  {delta === null ? "-" : `${delta > 0 ? "+" : ""}${fmt(delta)}`}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
        placeholder="What did you count, and why does it differ? (required)"
        className="mt-4 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
      <Button className="mt-3 h-12 w-full justify-center"
        disabled={busy || !lines.length || !note.trim()}
        onClick={() => onSubmit({ rows: lines, note })}>
        Apply count · {lines.length} line{lines.length === 1 ? "" : "s"}
      </Button>
    </Modal>
  )
}

function WasteModal({ rows, busy, onClose, onSubmit }: {
  rows: StockRow[]; busy: boolean; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  const [ingredient, setIngredient] = useState("")
  const [qty, setQty] = useState("")
  const [note, setNote] = useState("")
  const row = rows.find((r) => r.ingredient === ingredient)
  return (
    <Modal title="Record wastage" onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">
        Stock destroyed outside a sale - spoiled, broken, dropped. Food that was
        cooked and then voided is already accounted for; it shows in the wastage
        report on its own.
      </p>
      <div className="space-y-3">
        <select className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          value={ingredient} onChange={(e) => setIngredient(e.target.value)}>
          <option value="">Pick an ingredient…</option>
          {rows.map((r) => (
            <option key={r.name} value={r.ingredient}>
              {r.ingredient_name} - {fmt(r.qty_on_hand)} {r.uom} on hand
            </option>
          ))}
        </select>
        <input type="number" min="0" step="any" inputMode="decimal" value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder={row ? `Qty wasted (${row.uom})` : "Qty wasted"}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm tabular-nums" />
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder="What happened? (required)"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
      </div>
      <Button className="mt-4 h-12 w-full justify-center"
        disabled={busy || !ingredient || Number(qty) <= 0 || !note.trim()}
        onClick={() => onSubmit({ ingredient, qty: Number(qty), reason_note: note })}>
        Write it off
      </Button>
    </Modal>
  )
}

function LedgerModal({ row, outlet, onClose }: {
  row: StockRow; outlet: string; onClose: () => void
}) {
  const [entries, setEntries] = useState<LedgerRow[] | null>(null)
  useEffect(() => {
    call<LedgerRow[]>("kamra.inventory.ingredient_ledger", {
      property: getCurrentProperty(), outlet, ingredient: row.ingredient, limit: 50,
    }).then(setEntries).catch(() => setEntries([]))
  }, [row.ingredient, outlet])
  return (
    <Modal title={`${row.ingredient_name} · where it went`} onClose={onClose}>
      {entries === null ? (
        <p className="text-sm text-zinc-400">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-zinc-400">No movements yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-zinc-400">
            <tr><th className="pb-1">When</th><th className="pb-1">Reason</th>
              <th className="pb-1 text-right">Change</th><th className="pb-1 text-right">Balance</th>
              <th className="pb-1">Detail</th></tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {entries.map((e) => (
              <tr key={e.name}>
                <td className="py-1.5 whitespace-nowrap text-zinc-500">
                  {new Date(e.creation.replace(" ", "T")).toLocaleString([], {
                    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                  })}
                </td>
                <td className="py-1.5"><span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-bold text-zinc-600">{e.reason}</span></td>
                <td className={cn("py-1.5 text-right font-bold tabular-nums",
                  e.qty_change < 0 ? "text-rose-600" : "text-emerald-600")}>
                  {e.qty_change > 0 ? "+" : ""}{fmt(e.qty_change)}
                </td>
                <td className={cn("py-1.5 text-right tabular-nums",
                  e.balance_after < 0 ? "font-bold text-rose-600" : "text-zinc-500")}>
                  {fmt(e.balance_after)}
                </td>
                <td className="py-1.5 text-zinc-400">
                  {e.note || e.supplier || e.reference_name || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Modal>
  )
}
