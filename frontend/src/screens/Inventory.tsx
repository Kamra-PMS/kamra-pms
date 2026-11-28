import { useCallback, useEffect, useMemo, useState } from "react"
import {
  PackageSearch, RefreshCw, TriangleAlert, X, Truck, ClipboardCheck,
  Trash2, History, Ban, Plus, CookingPot,
} from "lucide-react"
import { call, frappeFetch, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useAuth } from "../lib/auth"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"
import { t as translate, useUILanguage, uiDateLocale } from "../lib/i18n"
import {
  defaultEntry, fmtUnitCost, receiveLine, receiveRow, type ReceiveEntry,
} from "../lib/stockCost"
import { enteredLater, postedAt } from "../lib/stockDates"
import { batchUse, type BatchLine } from "../lib/produce"
import StockSummary from "./StockSummary"

/* Kitchen stock. Two things here are deliberate and read as bugs if you don't
   know why:
    - Stock is PER OUTLET, so there is no merged "all outlets" total and this
       screen never offers one. There is no such number.
    - NEGATIVE is a valid state, not an error. It means the count is stale,
       and it is the loudest thing on the screen because it is the system
       admitting it doesn't know something. */

type Status = "OK" | "LOW" | "OUT" | "NEGATIVE"

interface StockRow {
  name: string | null
  /** 0 = this outlet has never moved it: offered in the pickers only. */
  stocked: 0 | 1
  ingredient: string
  ingredient_name: string
  uom: string
  buy_uom: string | null
  buy_size: number | null
  category: string | null
  cost_per_unit: number | null
  /** made in the kitchen from other ingredients: produced, never received */
  is_made: 0 | 1
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
  invoice_no: string | null
  outlet: string
  outlet_name?: string | null
  cost_per_unit: number | null
  purchase_qty: number | null
  purchase_uom: string | null
  purchase_size: number | null
  purchase_price: number | null
  /** "" = a delivery recorded before prices were kept this way */
  price_entry: "" | "Entered" | "Not entered" | null
  cost_after: number | null
  posted_at: string | null
  owner: string
  /** every ingredient in this line's delivery or stock take */
  batch_ingredients: string[]
  cancelled: 0 | 1
  cancelled_by: string | null
  cancelled_at: string | null
  cancel_reason: string | null
  original_qty_change: number | null
}
interface LowRow {
  ingredient: string
  ingredient_name: string
  uom: string
  qty_on_hand: number
  status: Status
  dishes: { name: string; item_name: string; available: 0 | 1 }[]
  /** names of what is made from this ingredient */
  makes: string[]
}

const WRITE_ROLES = ["Finance", "F&B Manager", "Hotel Admin", "System Manager", "Administrator"]
const CANCEL_ROLES = ["Hotel Admin", "System Manager", "Administrator"]
/** What was typed by hand can be taken back; kitchen and banquet usage cannot. */
const CANCELLABLE = ["Received", "Count", "Wastage", "Production"]
function cancelWords(reason: string) {
  if (reason === "Production") return { ask: translate("Cancel this whole batch?"), yes: translate("Cancel batch") }
  if (reason === "Received") return { ask: translate("Cancel this whole delivery?"), yes: translate("Cancel delivery") }
  if (reason === "Count") return { ask: translate("Cancel this whole stock take?"), yes: translate("Cancel stock take") }
  return { ask: translate("Cancel this wastage?"), yes: translate("Cancel wastage") }
}
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
  return d <= 0 ? translate("today") : d === 1 ? translate("yesterday") : translate("{n}d ago", { n: String(d) })
}
const fmt = (n: number) => (Math.round(n * 1000) / 1000).toString()

function StatusChip({ s }: { s: Status }) {
  useUILanguage()
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide", TONE[s])}>
      {s === "NEGATIVE" && <TriangleAlert className="size-3" />}{translate(s)}
    </span>
  )
}

/** When a stock entry happened. Left empty, it happens now. */
function DateField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  useUILanguage()
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
  // the hotel may limit how far back an entry can be dated; the server decides
  const [earliest, setEarliest] = useState<string | null>(null)
  useEffect(() => {
    call<{ earliest: string | null }>("kamra.inventory.entry_limit", { property: getCurrentProperty() })
      .then((r) => setEarliest(r.earliest)).catch(() => {})
  }, [])
  return (
    <label className="mb-3 flex flex-wrap items-center gap-2 text-sm text-zinc-600">
      <span className="font-medium">{translate("Date and time")}</span>
      <input type="datetime-local" min={earliest ? `${earliest}T00:00` : undefined} max={now}
        value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm tabular-nums" />
      {!value && <span className="text-xs text-zinc-400">{translate("Leave empty for now.")}</span>}
      {earliest && (
        <span className="text-xs text-zinc-400">
          {translate("Earliest: {date}", {
            date: new Date(`${earliest}T00:00`).toLocaleDateString(uiDateLocale([]), { dateStyle: "medium" }),
          })}
        </span>
      )}
    </label>
  )
}

function Refusal({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <div role="alert" className="mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">
      {error}
    </div>
  )
}

function Modal({ title, onClose, wide, children }: {
  title: string; onClose: () => void; wide?: boolean; children: React.ReactNode
}) {
  useUILanguage()
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 p-4">
      <div className={cn("flex max-h-[85vh] w-full flex-col rounded-2xl bg-white shadow-2xl",
        wide ? "max-w-4xl" : "max-w-2xl")}>
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <h2 className="text-lg font-bold text-zinc-800">{translate(title)}</h2>
          <button onClick={onClose} aria-label={translate("Close")}
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
  useUILanguage()
  const { allowed } = useAuth()
  const canWrite = allowed("Ingredient", "manage_stock", WRITE_ROLES)
  const canCancel = allowed("Ingredient", "cancel_stock", CANCEL_ROLES)

  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [outlet, setOutlet] = useState("")
  // Every active ingredient, so Receive can take a new one in. The table,
  // stock take and wastage start from what this outlet holds.
  const [shelf, setShelf] = useState<StockRow[]>([])
  const rows = useMemo(() => shelf.filter((r) => r.stocked), [shelf])
  const [low, setLow] = useState<LowRow[]>([])
  const [filter, setFilter] = useState<Status | "">("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [modal, setModal] = useState<"receive" | "count" | "waste" | null>(null)
  // the Produce window: "" to pick what was made, or the ingredient chosen
  const [producing, setProducing] = useState<string | null>(null)
  const makesHere = shelf.some((r) => r.is_made)
  // the history window: one ingredient at one outlet, maybe for one period
  const [ledgerOf, setLedgerOf] = useState<History | null>(null)
  const [view, setView] = useState<"stock" | "summary">("stock")
  const [parOf, setParOf] = useState<StockRow | null>(null)

  useEffect(() => {
    call<{ name: string; outlet_name: string }[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then((o) => { setOutlets(o); if (o.length && !outlet) setOutlet(o[0].name) })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = useCallback(() => {
    if (!outlet) return
    const property = getCurrentProperty()
    call<StockRow[]>("kamra.inventory.stock_list", { property, outlet, include_unstocked: 1 })
      .then(setShelf).catch((e) => setErr(String(e)))
    call<LowRow[]>("kamra.inventory.low_stock", { property, outlet })
      .then(setLow).catch(() => {})
  }, [outlet])

  useEffect(() => { load() }, [load])

  const act = useCallback(async (method: string, params: Record<string, unknown>) => {
    setBusy(true); setErr(null)
    try {
      await call(`kamra.inventory.${method}`, { property: getCurrentProperty(), outlet, ...params })
      setModal(null)
      setProducing(null)
      setParOf(null)
      load()
    } catch (e) {
      setErr(e instanceof Error ? translate(e.message) : String(e))
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
          <PackageSearch className="size-5 text-brand-600" />{translate("Kitchen inventory")}</h1>
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
              {/* reloaded on opening: a delivery is refused when a buying unit changed since */}
              <Button variant="outline" onClick={() => { setErr(null); load(); setModal("receive") }}>
                <Truck className="size-4" />{translate("Receive")}</Button>
              <Button variant="outline" onClick={() => { setErr(null); load(); setModal("count") }}>
                <ClipboardCheck className="size-4" />{translate("Stock take")}</Button>
              <Button variant="outline" onClick={() => { setErr(null); setModal("waste") }}>
                <Trash2 className="size-4" />{translate("Wastage")}</Button>
              {makesHere && (
                <Button variant="outline" onClick={() => { setErr(null); load(); setProducing("") }}>
                  <CookingPot className="size-4" />{translate("Produce")}</Button>
              )}
            </>
          )}
          <button onClick={load} aria-label={translate("Refresh")}><RefreshCw className="size-5 text-zinc-400" /></button>
        </div>
      </div>

      <div className="flex gap-1.5">
        {(["stock", "summary"] as const).map((k) => (
          <button key={k} type="button" aria-pressed={view === k} onClick={() => setView(k)}
            className={cn("rounded-lg px-3 py-1.5 text-sm font-medium",
              view === k ? "bg-brand-600 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
            {k === "stock" ? translate("Stock") : translate("Summary")}
          </button>
        ))}
      </div>
      {view === "summary" ? (
        <StockSummary key={getCurrentProperty()} outlets={outlets} outlet={outlet}
          onOpen={(r, from, to) => setLedgerOf({ row: r, outlet: r.outlet, period: { from, to } })} />
      ) : (<>
      {err && (
        <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">
          {translate(err)}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {(["", ...STATUSES] as const).map((s) => (
          <button key={s || "all"} onClick={() => setFilter(s as Status | "")}
            className={cn("rounded-lg px-3 py-1.5 text-sm font-medium",
              filter === s ? "bg-brand-600 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
            {translate(s) || translate("All")}{s ? ` · ${counts[s] ?? 0}` : ` · ${rows.length}`}
          </button>
        ))}
      </div>

      {/* What's out, and the dishes it takes down with it. The system flags
          and offers; a human decides. Nothing is ever auto-86'd. */}
      {low.length > 0 && (
        <div className="rounded-2xl border-2 border-amber-300 bg-amber-50/50 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-black uppercase tracking-wide text-amber-800">
            <TriangleAlert className="size-4" />{translate("Needs attention · ")}{low.length}
          </div>
          <ul className="space-y-2">
            {low.map((l) => (
              <li key={l.ingredient} className="flex flex-wrap items-center gap-2 text-sm">
                <StatusChip s={l.status} />
                <span className="font-bold text-zinc-800">{l.ingredient_name}</span>
                <span className="tabular-nums text-zinc-500">{fmt(l.qty_on_hand)} {l.uom}</span>
                {l.dishes.length > 0 && (
                  <span className="text-zinc-500">
                    → {l.dishes.filter((d) => d.available).map((d) => d.item_name).join(", ") || translate("no live dishes")}
                  </span>
                )}
                {l.makes.length > 0 && (
                  <span className="text-zinc-500">
                    {translate("Used to make: {names}", { names: l.makes.join(", ") })}
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
            ? translate("No ingredients stocked at this outlet yet. Add them under Ingredients, then Receive here.")
            : translate("Nothing in this state.")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-bold">{translate("Ingredient")}</th>
                <th className="px-4 py-2 font-bold">{translate("Category")}</th>
                <th className="px-4 py-2 text-right font-bold">{translate("On hand")}</th>
                <th className="px-4 py-2 text-right font-bold">{translate("Par")}</th>
                <th className="px-4 py-2 font-bold">{translate("Status")}</th>
                <th className="px-4 py-2 font-bold">{translate("Counted")}</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {shown.map((r) => (
                <tr key={r.name} className={cn(r.status === "NEGATIVE" && "bg-rose-50/60")}>
                  <td className="px-4 py-2 font-semibold text-zinc-800">{r.ingredient_name}</td>
                  <td className="px-4 py-2 text-zinc-500">{translate(r.category) || "-"}</td>
                  <td className={cn("px-4 py-2 text-right font-bold tabular-nums",
                    r.status === "NEGATIVE" ? "text-rose-600" : "text-zinc-800")}>
                    {fmt(r.qty_on_hand)} <span className="font-normal text-zinc-400">{r.uom}</span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-zinc-400">
                    {canWrite ? (
                      <Button type="button" variant="outline" onClick={() => setParOf(r)}
                        aria-label={translate("Low-stock level for {v0}", { v0: String(r.ingredient_name) })}
                        className="min-h-11 justify-end px-3">
                        <span className="tabular-nums">{r.par_level ? fmt(r.par_level) : "-"}</span>
                        {translate("Set")}
                      </Button>
                    ) : r.par_level ? fmt(r.par_level) : "-"}
                  </td>
                  <td className="px-4 py-2"><StatusChip s={r.status} /></td>
                  <td className="px-4 py-2 text-zinc-400">
                    {r.status === "NEGATIVE"
                      ? <span className="font-bold text-rose-600">{translate("recount")}{daysSince(r.last_counted_at) ? translate(" · last {v0}", { v0: String(daysSince(r.last_counted_at)) }) : translate(" · never counted")}</span>
                      : daysSince(r.last_counted_at) ?? translate("never")}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    {canWrite && !!r.is_made && (
                      <Button variant="ghost" className="h-8 px-2 text-xs"
                        onClick={() => { setErr(null); load(); setProducing(r.ingredient) }}>
                        <CookingPot className="size-3.5" />{translate("Produce")}</Button>
                    )}
                    <Button variant="ghost" className="h-8 px-2 text-xs"
                      onClick={() => setLedgerOf({ row: r, outlet })}>
                      <History className="size-3.5" />{translate("Ledger")}</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      </>)}

      {modal === "receive" && (
        <ReceiveModal rows={shelf.filter((r) => !r.is_made)} outlet={outlet} busy={busy} error={err}
          onClose={() => { setErr(null); setModal(null) }}
          onSubmit={(p) => act("receive_stock", p)} />
      )}
      {modal === "count" && (
        <CountModal rows={shelf} outlet={outlet} busy={busy} error={err}
          onClose={() => { setErr(null); setModal(null) }} onSubmit={(p) => act("adjust_stock", p)} />
      )}
      {modal === "waste" && (
        <WasteModal rows={shelf} busy={busy} error={err}
          onClose={() => { setErr(null); setModal(null) }} onSubmit={(p) => act("record_wastage", p)} />
      )}
      {producing !== null && (
        <ProduceModal rows={shelf} outlet={outlet} initial={producing} busy={busy} error={err}
          outletName={outlets.find((o) => o.name === outlet)?.outlet_name ?? outlet}
          onClose={() => { setErr(null); setProducing(null) }}
          onSubmit={(p) => act("produce", p)} />
      )}
      {parOf && (
        <ParModal row={parOf} busy={busy}
          onClose={() => setParOf(null)} onSubmit={(p) => act("set_par_level", p)} />
      )}
      {ledgerOf && (
        <LedgerModal {...ledgerOf} canCancel={canCancel} onChanged={load}
          onClose={() => setLedgerOf(null)} />
      )}
    </div>
  )
}

function ReceiveModal({ rows, busy, error, onClose, onSubmit }: {
  rows: StockRow[]; outlet: string; busy: boolean; error: string | null
  onClose: () => void; onSubmit: (p: Record<string, unknown>) => void
}) {
  useUILanguage()
  const [typed, setTyped] = useState<Record<string, ReceiveEntry>>({})
  const [supplier, setSupplier] = useState("")
  const [invoice, setInvoice] = useState("")
  const [when, setWhen] = useState("")
  const entryOf = (r: StockRow) => typed[r.ingredient] ?? defaultEntry(r)
  const edit = (r: StockRow, change: Partial<ReceiveEntry>) =>
    setTyped({ ...typed, [r.ingredient]: { ...entryOf(r), ...change } })
  const lines = rows.map((r) => receiveRow(r, entryOf(r))).filter((l) => l !== null)
  // a quantity typed against an empty pack size must not be dropped unnoticed
  const incomplete = rows.some((r) => Number(entryOf(r).qty) > 0 && !receiveLine(r, entryOf(r)))
  const box = "w-24 rounded border border-zinc-300 px-2 py-1 tabular-nums"
  return (
    <Modal title={translate("Receive stock")} onClose={onClose} wide>
      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <input className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          placeholder={translate("Supplier")} value={supplier} onChange={(e) => setSupplier(e.target.value)} />
        <input className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          placeholder={translate("Invoice no")} value={invoice} onChange={(e) => setInvoice(e.target.value)} />
      </div>
      <DateField value={when} onChange={setWhen} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-zinc-400">
            <tr>
              <th className="pb-1 pr-2">{translate("Ingredient")}</th>
              <th className="pb-1 pr-2">{translate("Qty in")}</th>
              <th className="pb-1 pr-2">{translate("Unit")}</th>
              <th className="pb-1 pr-2">{translate("Holds")}</th>
              <th className="pb-1 pr-2">{translate("Price per unit")}</th>
              <th className="pb-1">{translate("Goes into stock")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rows.map((r) => {
              const e = entryOf(r)
              const line = receiveLine(r, e)
              const size = e.unit === "buy" ? Number(e.size) || 0 : 1
              const current = r.cost_per_unit && size
                ? String(Math.round(r.cost_per_unit * size * 10000) / 10000) : "-"
              const vars = line ? { qty: fmt(line.stockQty), uom: r.uom } : null
              return (
                <tr key={r.ingredient}>
                  <td className="py-1.5 pr-2 font-medium">{r.ingredient_name}</td>
                  <td className="py-1.5 pr-2"><input type="number" min="0" step="any" inputMode="decimal"
                    aria-label={`${r.ingredient_name} · ${translate("Qty in")}`}
                    className={box} value={e.qty} onChange={(ev) => edit(r, { qty: ev.target.value })} /></td>
                  <td className="py-1.5 pr-2">
                    {r.buy_uom && Number(r.buy_size) > 0 ? (
                      <select className="rounded border border-zinc-300 px-2 py-1"
                        aria-label={`${r.ingredient_name} · ${translate("Unit")}`}
                        value={e.unit}
                        onChange={(ev) => edit(r, ev.target.value === "buy"
                          ? { unit: "buy", size: String(r.buy_size) } : { unit: "stock" })}>
                        <option value="buy">{r.buy_uom} ({fmt(Number(r.buy_size))} {r.uom})</option>
                        <option value="stock">{r.uom}</option>
                      </select>
                    ) : <span className="text-zinc-500">{r.uom}</span>}
                  </td>
                  <td className="py-1.5 pr-2 whitespace-nowrap">
                    {e.unit === "buy" && (
                      <>
                        <input type="number" min="0" step="any" inputMode="decimal"
                          aria-label={`${r.ingredient_name} · ${translate("Holds")}`}
                          className="w-20 rounded border border-zinc-300 px-2 py-1 tabular-nums"
                          value={e.size} onChange={(ev) => edit(r, { size: ev.target.value })} />
                        <span className="ml-1 text-xs text-zinc-400">{r.uom}</span>
                      </>
                    )}
                  </td>
                  <td className="py-1.5 pr-2"><input type="number" min="0" step="any" inputMode="decimal"
                    aria-label={`${r.ingredient_name} · ${translate("Price per unit")}`}
                    className={box} placeholder={current}
                    value={e.price} onChange={(ev) => edit(r, { price: ev.target.value })} /></td>
                  <td className="py-1.5 text-xs tabular-nums text-zinc-500">
                    {line && vars
                      ? line.perUnit === null
                        ? translate("+{qty} {uom}, no price", vars)
                        : translate("+{qty} {uom} at {price} each, {total} in all", {
                            ...vars, price: fmtUnitCost(line.perUnit), total: fmtUnitCost(line.total),
                          })
                      : Number(e.qty) > 0 && (
                        <span className="font-bold text-rose-600">{translate("Holds must be above zero.")}</span>
                      )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-zinc-400">{translate("A price updates the ingredient's cost as Settings, F&B says: the last price paid, or the average of purchases. Leave it empty to keep the cost.")}</p>
      <Refusal error={error} />
      <Button className="mt-4 h-12 w-full justify-center" disabled={busy || !lines.length || incomplete}
        onClick={() => onSubmit({ rows: lines, supplier: supplier || null, invoice_no: invoice || null, posted_at: postedAt(when) })}>{translate("Receive ")}{lines.length || ""}{translate(" ingredient")}{lines.length === 1 ? "" : translate("s")}
      </Button>
    </Modal>
  )
}

function CountModal({ rows, outlet, busy, error, onClose, onSubmit }: {
  rows: StockRow[]; outlet: string; busy: boolean; error: string | null; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  useUILanguage()
  const [counted, setCounted] = useState<Record<string, string>>({})
  const [note, setNote] = useState("")
  const [added, setAdded] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [when, setWhen] = useState("")
  // a count dated in the past is compared with what the shelf held then
  const at = postedAt(when)
  const [past, setPast] = useState<{ at: string; held: Record<string, number> } | null>(null)
  useEffect(() => {
    if (!at) return
    let live = true
    call<Record<string, number>>("kamra.inventory.stock_at", { property: getCurrentProperty(), outlet, at })
      .then((held) => { if (live) setPast({ at, held }) })
      .catch(() => {})
    return () => { live = false }
  }, [at, outlet])
  const expected = (r: StockRow) =>
    !at ? r.qty_on_hand : past?.at === at ? past.held[r.ingredient] ?? 0 : null
  const shown = heldMatching(rows, added, query)
  const lines = Object.entries(counted)
    .filter(([, v]) => v !== "")
    .map(([ingredient, v]) => ({ ingredient, counted_qty: Number(v) }))
  return (
    <Modal title={translate("Stock take")} onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">{translate("Count what's physically on the shelf. Leave a row blank to skip it.")}</p>
      <DateField value={when} onChange={setWhen} />
      <ShelfTools rows={rows} query={query} onQuery={setQuery} added={added}
        onAdd={(id) => { setAdded((prev) => prev.includes(id) ? prev : [...prev, id]); setQuery("") }} />
      {shown.length === 0 ? (
        <p className="py-6 text-center text-sm text-zinc-400">
          {query.trim() ? translate("No matches.") : translate("Nothing stocked at this outlet yet.")}
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-zinc-400">
            <tr><th className="pb-1">{translate("Ingredient")}</th><th className="pb-1 pr-6 text-right">{translate("System")}</th>
              <th className="pb-1">{translate("Counted")}</th><th className="pb-1 text-right">{translate("Variance")}</th></tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {shown.map((r) => {
              const v = counted[r.ingredient]
              const system = expected(r)
              const delta = v === "" || v === undefined || system === null ? null : Number(v) - system
              return (
                <tr key={r.ingredient}>
                  <td className="py-1.5 font-medium">{r.ingredient_name}
                    <span className="ml-1 text-xs text-zinc-400">{r.uom}</span></td>
                  <td className="py-1.5 pr-6 text-right tabular-nums text-zinc-400">{system === null ? "…" : fmt(system)}</td>
                  <td className="py-1.5">
                    {/* Deliberately blank, never pre-filled with the system qty:
                        pre-filling invites blind confirmation, which is exactly
                        how a count rots into fiction. */}
                    <input type="number" step="any" inputMode="decimal" placeholder={translate("count…")}
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
      )}
      <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
        placeholder={translate("What did you count, and why does it differ? (required)")}
        className="mt-4 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
      <Refusal error={error} />
      <Button className="mt-3 h-12 w-full justify-center"
        disabled={busy || !lines.length || !note.trim()}
        onClick={() => onSubmit({ rows: lines, note, posted_at: at })}>{translate("Apply count · ")}{lines.length}{translate(" line")}{lines.length === 1 ? "" : translate("s")}
      </Button>
    </Modal>
  )
}

function WasteModal({ rows, busy, error, onClose, onSubmit }: {
  rows: StockRow[]; busy: boolean; error: string | null; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  useUILanguage()
  const [ingredient, setIngredient] = useState("")
  const [qty, setQty] = useState("")
  const [note, setNote] = useState("")
  const [added, setAdded] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [when, setWhen] = useState("")
  const shown = heldMatching(rows, added, query)
  const row = rows.find((r) => r.ingredient === ingredient)
  // Keep a chosen row in the list even while a search hides its name.
  const options = row && !shown.some((r) => r.ingredient === row.ingredient)
    ? [row, ...shown] : shown
  return (
    <Modal title={translate("Record wastage")} onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">{translate("Stock destroyed outside a sale - spoiled, broken, dropped. Food that was cooked and then voided is already accounted for; it shows in the wastage report on its own.")}</p>
      <ShelfTools rows={rows} query={query} onQuery={setQuery} added={added}
        onAdd={(id) => {
          setAdded((prev) => prev.includes(id) ? prev : [...prev, id])
          setIngredient(id)
          setQuery("")
        }} />
      <div className="space-y-3">
        {options.length === 0 ? (
          <p className="text-sm text-zinc-400">
            {query.trim() ? translate("No matches.") : translate("Nothing stocked at this outlet yet.")}
          </p>
        ) : (
          <select className="min-h-11 w-full rounded-lg border border-zinc-300 px-3 text-sm"
            value={ingredient} onChange={(e) => setIngredient(e.target.value)}>
            <option value="">{translate("Pick an ingredient…")}</option>
            {options.map((r) => (
              <option key={r.ingredient} value={r.ingredient}>
                {r.ingredient_name} - {fmt(r.qty_on_hand)} {r.uom}{translate(" on hand")}</option>
            ))}
          </select>
        )}
        {row && row.stocked === 0 && (
          <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {translate("This outlet has never held this ingredient. Writing it off will take the balance below zero.")}
          </div>
        )}
        <input type="number" min="0" step="any" inputMode="decimal" value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder={(row ? translate("Qty wasted ({v0})", { v0: String(row.uom) }) : translate("Qty wasted"))}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm tabular-nums" />
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder={translate("What happened? (required)")}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
        <DateField value={when} onChange={setWhen} />
      </div>
      <Refusal error={error} />
      <Button className="mt-4 h-12 w-full justify-center"
        disabled={busy || !ingredient || Number(qty) <= 0 || !note.trim()}
        onClick={() => onSubmit({ ingredient, qty: Number(qty), reason_note: note, posted_at: postedAt(when) })}>{translate("Write it off")}</Button>
    </Modal>
  )
}

/** A batch made: what goes into stock, and what that takes off the shelf. Too
 *  little of something is warned about by name and can still be saved. */
function ProduceModal({ rows, outlet, outletName, initial, busy, error, onClose, onSubmit }: {
  rows: StockRow[]; outlet: string; outletName: string; initial: string
  busy: boolean; error: string | null; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  useUILanguage()
  const made = rows.filter((r) => r.is_made)
  const [picked, setPicked] = useState(initial)
  const ingredient = picked || (made.length === 1 ? made[0].ingredient : "")
  const row = rows.find((r) => r.ingredient === ingredient)
  const [qty, setQty] = useState("")
  const [note, setNote] = useState("")
  const [when, setWhen] = useState("")
  const [recipe, setRecipe] = useState<{ of: string; batch: number; lines: BatchLine[] } | null>(null)
  const [names, setNames] = useState<Record<string, { ingredient_name: string; uom: string }>>({})
  const [failed, setFailed] = useState<string | null>(null)
  useEffect(() => {
    call<{ name: string; ingredient_name: string; uom: string }[]>(
      "kamra.inventory.ingredients", { property: getCurrentProperty(), active_only: 0 })
      .then((list) => setNames(Object.fromEntries(list.map((i) => [i.name, i]))))
      .catch((e) => setFailed(serverError(e)))
  }, [])
  useEffect(() => {
    if (!ingredient) return
    let live = true
    frappeFetch<{ data: { batch_qty: number; recipe: BatchLine[] } }>(
      `/api/resource/Ingredient/${encodeURIComponent(ingredient)}`)
      .then((r) => { if (live) setRecipe({ of: ingredient, batch: r.data.batch_qty, lines: r.data.recipe }) })
      .catch((e) => { if (live) setFailed(serverError(e)) })
    return () => { live = false }
  }, [ingredient])
  // a batch dated in the past is set against what the shelf held then
  const at = postedAt(when)
  const [past, setPast] = useState<{ at: string; held: Record<string, number> } | null>(null)
  useEffect(() => {
    if (!at) return
    let live = true
    call<Record<string, number>>("kamra.inventory.stock_at", { property: getCurrentProperty(), outlet, at })
      .then((held) => { if (live) setPast({ at, held }) })
      .catch(() => {})
    return () => { live = false }
  }, [at, outlet])
  const uses = recipe && recipe.of === ingredient ? batchUse(recipe.lines, recipe.batch, Number(qty)) : []
  const onShelf = (id: string) =>
    !at ? rows.find((r) => r.ingredient === id)?.qty_on_hand ?? 0
      : past?.at === at ? past.held[id] ?? 0 : null

  return (
    <Modal title={translate("Produce")} onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">
        {translate("Record a batch made at {outlet}. It goes into stock, and what it is made from comes out.", { outlet: outletName })}
      </p>
      <div className="space-y-3">
        <select className="min-h-11 w-full rounded-lg border border-zinc-300 px-3 text-sm"
          aria-label={translate("Made here (semi-finished)")} value={ingredient}
          onChange={(e) => setPicked(e.target.value)}>
          <option value="">{translate("Pick an ingredient…")}</option>
          {made.map((r) => (
            <option key={r.ingredient} value={r.ingredient}>
              {r.ingredient_name} - {fmt(r.qty_on_hand)} {r.uom}{translate(" on hand")}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-zinc-600">
          <span className="font-medium">{translate("Make")}</span>
          <input type="number" min="0" step="any" inputMode="decimal" value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-32 rounded-lg border border-zinc-300 px-3 py-2 tabular-nums" />
          <span>{row?.uom}</span>
        </label>
        <DateField value={when} onChange={setWhen} />
        {uses.length > 0 && (
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
            <div className="mb-1 font-medium text-zinc-600">{translate("This uses:")}</div>
            <ul className="space-y-1">
              {uses.map((u) => {
                const have = onShelf(u.ingredient)
                const short = have !== null && have - u.qty < -1e-9
                const uom = names[u.ingredient]?.uom ?? ""
                return (
                  <li key={u.ingredient} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{names[u.ingredient]?.ingredient_name ?? u.ingredient}</span>
                    <span className="tabular-nums">
                      <b>{fmt(u.qty)}</b> {uom}
                      {short && (
                        <span className="ms-2 text-xs font-bold text-rose-600">
                          {translate("{qty} {uom} there: goes below zero", { qty: fmt(have), uom })}
                        </span>
                      )}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder={translate("Note")} aria-label={translate("Note")}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
      </div>
      <Refusal error={error ?? (failed && translate(failed))} />
      <Button className="mt-4 h-12 w-full justify-center" disabled={busy || !uses.length}
        onClick={() => onSubmit({ ingredient, qty: Number(qty), note: note.trim() || null, posted_at: at })}>
        {translate("Produce")}</Button>
    </Modal>
  )
}

/** Stock take and wastage start from what this outlet holds. Search narrows
 *  that list; Add ingredient pulls in one the outlet has never moved. */
function heldMatching(rows: StockRow[], added: string[], query: string): StockRow[] {
  const q = query.trim().toLowerCase()
  const working = rows.filter((r) => r.stocked || added.includes(r.ingredient))
  if (!q) return working
  return working.filter((r) => (r.ingredient_name || "").toLowerCase().includes(q))
}

function ShelfTools({ rows, query, onQuery, added, onAdd }: {
  rows: StockRow[]
  query: string
  onQuery: (q: string) => void
  added: string[]
  onAdd: (ingredient: string) => void
}) {
  useUILanguage()
  const [adding, setAdding] = useState(false)
  const [addQuery, setAddQuery] = useState("")
  const q = addQuery.trim().toLowerCase()
  // Don't list every active ingredient: matches appear only after a search.
  const matches = q
    ? rows.filter((r) => !r.stocked && !added.includes(r.ingredient)
      && (r.ingredient_name || "").toLowerCase().includes(q)).slice(0, 8)
    : []
  return (
    <div className="mb-3 space-y-2">
      <input
        className="min-h-11 w-full rounded-lg border border-zinc-300 px-3 text-sm"
        placeholder={translate("Search…")}
        aria-label={translate("Search…")}
        value={query}
        onChange={(e) => onQuery(e.target.value)}
      />
      {adding ? (
        <div className="space-y-2">
          <input
            autoFocus
            className="min-h-11 w-full rounded-lg border border-zinc-300 px-3 text-sm"
            placeholder={translate("Add ingredient")}
            aria-label={translate("Add ingredient")}
            value={addQuery}
            onChange={(e) => setAddQuery(e.target.value)}
          />
          {q && matches.length === 0 && (
            <p className="text-sm text-zinc-400">{translate("No matches.")}</p>
          )}
          {matches.length > 0 && (
            <ul className="overflow-hidden rounded-lg border border-zinc-200">
              {matches.map((r) => (
                <li key={r.ingredient} className="border-b border-zinc-100 last:border-b-0">
                  <button type="button"
                    className="flex min-h-11 w-full items-center justify-between px-3 text-left text-sm hover:bg-zinc-50"
                    onClick={() => { onAdd(r.ingredient); setAddQuery(""); setAdding(false) }}>
                    <span className="font-medium text-zinc-800">{r.ingredient_name}</span>
                    <span className="text-xs text-zinc-400">{r.uom}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <Button type="button" variant="outline" className="min-h-11" onClick={() => setAdding(true)}>
          <Plus className="size-4" />{translate("Add ingredient")}
        </Button>
      )}
    </div>
  )
}

function ParModal({ row, busy, onClose, onSubmit }: {
  row: StockRow; busy: boolean; onClose: () => void
  onSubmit: (p: Record<string, unknown>) => void
}) {
  useUILanguage()
  const [level, setLevel] = useState(row.par_level ? String(row.par_level) : "")
  const valid = level !== "" && Number(level) >= 0
  return (
    <Modal title={translate("{v0} · low-stock level", { v0: String(row.ingredient_name) })} onClose={onClose}>
      <p className="mb-3 text-sm text-zinc-500">{translate("This ingredient shows as LOW when the stock on hand is at or below this level. Enter 0 for no warning.")}</p>
      <input type="number" min="0" step="any" inputMode="decimal" autoFocus value={level}
        onChange={(e) => setLevel(e.target.value)}
        placeholder={translate("Level ({v0})", { v0: String(row.uom) })}
        className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm tabular-nums" />
      <Button className="mt-4 h-12 w-full justify-center" disabled={busy || !valid}
        onClick={() => onSubmit({ ingredient: row.ingredient, par_level: Number(level) })}>{translate("Save level")}</Button>
    </Modal>
  )
}

/** What a delivery cost per stock unit, when it was given a price (or, on an
 *  older line, the price it stored). */
function pricedAt(e: LedgerRow): number | null {
  if (e.reason !== "Received" || e.price_entry === "Not entered") return null
  const cost = Number(e.cost_per_unit ?? 0)
  return e.price_entry === "Entered" || cost > 0 ? cost : null
}

interface History {
  row: Pick<StockRow, "ingredient" | "ingredient_name" | "uom">
  outlet: string
  period?: { from: string; to: string }
}

function LedgerModal({ row, outlet, period, canCancel, onChanged, onClose }: History & {
  canCancel: boolean; onChanged: () => void; onClose: () => void
}) {
  useUILanguage()
  const [tab, setTab] = useState<"all" | "purchases">("all")
  const [loaded, setLoaded] = useState<{ tab: string; entries: LedgerRow[] } | null>(null)
  const [asking, setAsking] = useState<LedgerRow | null>(null)
  const [version, setVersion] = useState(0)
  const [kept, setKept] = useState<string[]>([])
  useEffect(() => {
    let live = true
    call<LedgerRow[]>("kamra.inventory.ingredient_ledger", {
      property: getCurrentProperty(), outlet, ingredient: row.ingredient, limit: period ? 500 : 50,
      purchases_only: tab === "purchases" ? 1 : 0,
      from_date: period?.from, to_date: period?.to,
    }).then((entries) => { if (live) setLoaded({ tab, entries }) })
      .catch(() => { if (live) setLoaded({ tab, entries: [] }) })
    return () => { live = false }
  }, [row.ingredient, outlet, tab, version, period?.from, period?.to])
  const entries = loaded && loaded.tab === tab ? loaded.entries : null
  // a cancelled line moves nothing now: show what it had moved
  const change = (e: LedgerRow) => Number(e.cancelled ? e.original_qty_change ?? 0 : e.qty_change)
  const when = (iso: string) => new Date(iso.replace(" ", "T")).toLocaleString(uiDateLocale([]), {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  })
  return (
    <Modal title={translate("{v0} · where it went", { v0: String(row.ingredient_name) })} onClose={onClose} wide>
      {period && (
        <p className="mb-2 text-xs text-zinc-500">{translate("{from} to {to}", period)}</p>
      )}
      <div className="mb-3 flex gap-1.5">
        {(["all", "purchases"] as const).map((k) => (
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}
            className={cn("rounded-lg px-3 py-1.5 text-sm font-medium",
              tab === k ? "bg-brand-600 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
            {k === "all" ? translate("All movements") : translate("Purchases")}
          </button>
        ))}
      </div>
      {asking && (
        <CancelAsk entry={asking} onKeep={() => setAsking(null)}
          onDone={(unchanged) => { setAsking(null); setKept(unchanged); setVersion((v) => v + 1); onChanged() }} />
      )}
      {kept.length > 0 && (
        <div role="status" className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {translate("Cost not changed: it has moved since. Check it on the ingredient.")} ({kept.join(", ")})
        </div>
      )}
      {entries === null ? (
        <p className="text-sm text-zinc-400">{translate("Loading…")}</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-zinc-400">
          {tab === "all" ? translate("No movements yet.") : translate("No deliveries yet.")}
        </p>
      ) : tab === "purchases" ? (
        <Purchases entries={entries} uom={row.uom} when={when} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-zinc-400">
              <tr><th className="pb-1">{translate("When")}</th><th className="pb-1">{translate("Reason")}</th>
                <th className="pb-1 text-right">{translate("Change")}</th><th className="pb-1 text-right">{translate("Balance")}</th>
                <th className="pb-1 pl-3">{translate("Detail")}</th><th className="pb-1"></th></tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {entries.map((e) => {
                const price = pricedAt(e)
                return (
                  <tr key={e.name} className={cn(!!e.cancelled && "text-zinc-400 [&_td:not(.keep)]:line-through")}>
                    <td className="py-1.5 whitespace-nowrap text-zinc-500">{when(e.posted_at || e.creation)}</td>
                    <td className="py-1.5"><span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-bold text-zinc-600">{translate(e.reason)}</span></td>
                    <td className={cn("py-1.5 text-right font-bold tabular-nums",
                      e.cancelled ? "text-zinc-400" : e.qty_change < 0 ? "text-rose-600" : "text-emerald-600")}>
                      {change(e) > 0 ? "+" : ""}{fmt(change(e))}
                    </td>
                    <td className={cn("py-1.5 text-right tabular-nums",
                      e.balance_after < 0 ? "font-bold text-rose-600" : "text-zinc-500")}>
                      {e.cancelled ? "" : fmt(e.balance_after)}
                    </td>
                    <td className="keep py-1.5 pl-3 text-zinc-400">
                      {/* the old line is struck through; the note that says why stays readable */}
                      <div className={cn(!!e.cancelled && "line-through")}>
                      {price !== null && (
                        <span className="mr-2 whitespace-nowrap font-medium tabular-nums text-zinc-600">
                          {fmtUnitCost(price)} / {row.uom}</span>
                      )}
                      {e.note || e.supplier || e.reference_name || (price === null ? "-" : "")}
                      {enteredLater(e) && (
                        <div className="text-xs">{translate("entered {when} by {who}", { when: when(e.creation), who: e.owner })}</div>
                      )}
                      </div>
                      {e.cancelled ? (
                        <div className="text-xs font-medium text-rose-600">{translate("Cancelled {when} by {who}: {why}", {
                          when: when(e.cancelled_at || e.creation), who: e.cancelled_by ?? "", why: e.cancel_reason ?? "",
                        })}</div>
                      ) : null}
                    </td>
                    <td className="py-1.5 text-right">
                      {canCancel && !e.cancelled && CANCELLABLE.includes(e.reason) && (
                        <Button variant="outline" className="h-8 px-2 text-xs"
                          onClick={() => { setKept([]); setAsking(e) }}>{translate("Cancel")}</Button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}

/** Asks once, with a reason, before a whole entry is taken back. */
function CancelAsk({ entry, onKeep, onDone }: {
  entry: LedgerRow; onKeep: () => void; onDone: (costKept: string[]) => void
}) {
  useUILanguage()
  const [why, setWhy] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const words = cancelWords(entry.reason)
  const what = [
    [entry.supplier, entry.invoice_no].filter(Boolean).join(" "),
    (entry.batch_ingredients ?? []).join(", "),
  ].filter(Boolean).join(": ")
  const go = async () => {
    setBusy(true); setError(null)
    try {
      const r = await call<{ cost_unchanged: string[] }>("kamra.inventory.cancel_stock_entry", {
        property: getCurrentProperty(), entry: entry.name, reason: why,
      })
      onDone(r.cost_unchanged)
    } catch (e) {
      setError(e instanceof Error ? translate(e.message) : String(e))
      setBusy(false)
    }
  }
  return (
    <div className="mb-3 rounded-xl border-2 border-rose-200 bg-rose-50/60 p-3">
      <div className="text-sm font-bold text-zinc-800">{words.ask}</div>
      {what && <div className="text-sm text-zinc-600">{what}</div>}
      <input autoFocus value={why} onChange={(e) => setWhy(e.target.value)}
        placeholder={translate("Reason (required)")} aria-label={translate("Reason (required)")}
        className="mt-2 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm" />
      <Refusal error={error} />
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="outline" onClick={onKeep}>{translate("Keep it")}</Button>
        <Button disabled={busy || !why.trim()} onClick={go}>{words.yes}</Button>
      </div>
    </div>
  )
}

/** Deliveries only, from every outlet: what was bought, for how much, from whom. */
function Purchases({ entries, uom, when }: {
  entries: LedgerRow[]; uom: string; when: (iso: string) => string
}) {
  useUILanguage()
  const older = entries.some((e) => !e.price_entry)
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-zinc-400">
            <tr>
              <th className="pb-1 pr-3">{translate("Date")}</th>
              <th className="pb-1 pr-3">{translate("Outlet")}</th>
              <th className="pb-1 pr-3">{translate("Bought")}</th>
              <th className="pb-1 pr-3 text-right">{translate("Price")}</th>
              <th className="pb-1 pr-3 text-right">{translate("Per unit")}</th>
              <th className="pb-1 pr-3">{translate("Supplier, invoice")}</th>
              <th className="pb-1 text-right">{translate("Cost after")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {entries.map((e) => {
              const price = pricedAt(e)
              const packed = !!e.price_entry && !!e.purchase_uom && e.purchase_uom !== uom
              return (
                <tr key={e.name} className={cn(!!e.cancelled && "text-zinc-400 [&_td:not(:first-child)]:line-through")}>
                  <td className="py-1.5 pr-3 whitespace-nowrap text-zinc-500">
                    {when(e.posted_at || e.creation)}
                    {e.cancelled ? <span className="ml-1 text-xs font-bold text-rose-600">{translate("Cancelled")}</span> : null}
                  </td>
                  <td className="py-1.5 pr-3">{e.outlet_name || e.outlet}</td>
                  <td className="py-1.5 pr-3 whitespace-nowrap tabular-nums">
                    {packed
                      ? `${fmt(Number(e.purchase_qty))} ${e.purchase_uom} x ${fmt(Number(e.purchase_size))} = ${fmt(Number(e.cancelled ? e.original_qty_change : e.qty_change))} ${uom}`
                      : `${fmt(Number(e.cancelled ? e.original_qty_change : e.qty_change))} ${uom}`}
                  </td>
                  <td className="py-1.5 pr-3 whitespace-nowrap text-right tabular-nums">
                    {price === null ? "-"
                      : e.price_entry
                        ? `${fmtUnitCost(e.purchase_price)} / ${e.purchase_uom}`
                        : `${fmtUnitCost(price)} / ${uom}`}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{price === null ? "-" : fmtUnitCost(price)}</td>
                  <td className="py-1.5 pr-3 text-zinc-500">
                    {[e.supplier, e.invoice_no].filter(Boolean).join(", ") || "-"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {e.price_entry ? fmtUnitCost(e.cost_after) : ""}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {older && (
        <p className="mt-3 text-xs text-zinc-400">{translate("Older deliveries may show a price copied from an earlier one.")}</p>
      )}
    </>
  )
}
