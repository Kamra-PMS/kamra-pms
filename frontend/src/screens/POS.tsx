import { useCallback, useEffect, useRef, useState } from "react"
import {
  Plus, Minus, Trash2, Send, UtensilsCrossed, Leaf, Search,
  Maximize2, Minimize2, Wallet, ChevronLeft, ChevronRight,
  Printer, Receipt, XCircle, Ban, Scissors, Users,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { serverError } from "../lib/resource"
import { printThermal, kotHtml, billHtml, type BillData } from "../lib/thermal"
import { Button } from "../components/ui/button"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

interface MenuItem {
  name: string
  item_name: string
  category: string
  price: number
  is_veg: number
  image: string | null
}
interface Outlet { name: string; outlet_name: string }
interface OpenOrder {
  name: string
  label: string
  status: string
  order_total: number
  items: number
  pending: number
  kot_fired: number
  kot_no: number | null
  order_type: string | null
}
interface TableBill {
  order: string
  label: string
  order_total: number
  state: "running" | "fired" | "ready"
}
interface TableTile {
  table: string
  state: "vacant" | "running" | "fired" | "ready"
  bills: number
  order_total?: number
  orders: TableBill[]
}
interface CartLine {
  menu_item: string
  item_name: string
  price: number
  is_veg: number
  qty: number
  instructions: string
}
interface OrderItem {
  row: string
  item_name: string
  qty: number
  amount: number
  instructions: string | null
  kot_status: string
  voided: number
}
interface Detail {
  name: string
  status: string
  table_no: string | null
  room: string | null
  order_type: string | null
  kot_no: number | null
  paid: number
  payment_mode: string | null
  discount_amount: number
  subtotal: number
  order_total: number
  items: OrderItem[]
}

type OrderType = "Dine In" | "Room Service" | "Takeaway"
const ORDER_TYPES: OrderType[] = ["Dine In", "Room Service", "Takeaway"]

const TILE: Record<TableTile["state"], string> = {
  vacant: "border-dashed border-zinc-300 bg-white text-zinc-500 hover:border-brand-400 hover:text-brand-700",
  running: "border-amber-300 bg-amber-50 text-amber-900 hover:border-amber-400",
  fired: "border-sky-300 bg-sky-50 text-sky-900 hover:border-sky-400",
  ready: "border-emerald-300 bg-emerald-50 text-emerald-900 hover:border-emerald-400",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function POS() {
  const rootRef = useRef<HTMLDivElement>(null)
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outlet, setOutlet] = useState("")
  const [rooms, setRooms] = useState<{ name: string; room_number: string }[]>([])
  const [cats, setCats] = useState<{ category: string; items: MenuItem[] }[]>([])
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState<OpenOrder[]>([])
  const [tables, setTables] = useState<TableTile[]>([])
  const [selected, setSelected] = useState<string | null>(null) // null = new order
  const [detail, setDetail] = useState<Detail | null>(null)
  const [orderType, setOrderType] = useState<OrderType>("Dine In")
  const [room, setRoom] = useState("")
  const [table, setTable] = useState("")
  const [cart, setCart] = useState<CartLine[]>([]) // new lines (new order OR next round)
  const [discount, setDiscount] = useState("")
  const [printKot, setPrintKot] = useState(() => localStorage.getItem("pos_print_kot") !== "0")
  const [settling, setSettling] = useState(false)
  const [voiding, setVoiding] = useState<OrderItem | null>(null)
  const [voidReason, setVoidReason] = useState("")
  const [cancelling, setCancelling] = useState(false)
  const [cancelReason, setCancelReason] = useState("")
  const [chooser, setChooser] = useState<string | null>(null) // table with several bills
  const [splitMode, setSplitMode] = useState(false)
  const [splitSel, setSplitSel] = useState<Set<string>>(new Set())
  const [customTable, setCustomTable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [full, setFull] = useState(false)

  useEffect(() => {
    call<Outlet[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then((o) => { setOutlets(o); if (o[0]) setOutlet(o[0].name) })
      .catch((e) => setError(serverError(e)))
    call<{ rooms: { name: string; room_number: string }[] }>("kamra.api.hk_queue", { property: getCurrentProperty() })
      .then((d) => setRooms(d.rooms || []))
      .catch(() => {})
    const onFs = () => setFull(!!document.fullscreenElement)
    document.addEventListener("fullscreenchange", onFs)
    return () => document.removeEventListener("fullscreenchange", onFs)
  }, [])

  useEffect(() => { localStorage.setItem("pos_print_kot", printKot ? "1" : "0") }, [printKot])

  const loadMenu = useCallback(() => {
    if (!outlet) return
    call<{ categories: { category: string; items: MenuItem[] }[] }>("kamra.pos.pos_menu", { outlet })
      .then((m) => setCats(m.categories)).catch((e) => setError(serverError(e)))
  }, [outlet])
  useEffect(loadMenu, [loadMenu])

  const loadOpen = useCallback(() => {
    if (!outlet) return
    call<OpenOrder[]>("kamra.pos.open_orders", { outlet }).then(setOpen).catch(() => {})
    call<{ tables: TableTile[] }>("kamra.pos.table_map", { outlet })
      .then((d) => setTables(d.tables)).catch(() => {})
  }, [outlet])
  useEffect(() => {
    loadOpen()
    const unsub = subscribeRealtime(loadOpen) // live tabs + table map across captains
    const t = setInterval(loadOpen, 20_000)
    return () => { unsub(); clearInterval(t) }
  }, [loadOpen])

  function resetPanel() {
    setCart([]); setDiscount(""); setSettling(false)
    setVoiding(null); setVoidReason(""); setCancelling(false); setCancelReason("")
    setSplitMode(false); setSplitSel(new Set()); setChooser(null)
  }
  function newOrder(atTable?: string) {
    setSelected(null); setDetail(null); setRoom(""); resetPanel()
    setTable(atTable || ""); setCustomTable(false)
    if (atTable) setOrderType("Dine In")
  }
  async function openTab(name: string) {
    setSelected(name); resetPanel()
    const d = await call<Detail>("kamra.pos.order_detail", { order: name })
    setDetail(d)
  }
  async function reloadDetail() {
    if (!selected) return
    const d = await call<Detail>("kamra.pos.order_detail", { order: selected })
    setDetail(d)
  }
  /** Step to the previous/next running order (wraps); from "New order" it
   * enters the list at the first/last tab. */
  function traverse(dir: 1 | -1) {
    if (open.length === 0) return
    const idx = selected === null ? -1 : open.findIndex((o) => o.name === selected)
    const next = idx === -1
      ? (dir === 1 ? 0 : open.length - 1)
      : (idx + dir + open.length) % open.length
    openTab(open[next].name)
  }

  const addToCart = (it: MenuItem) =>
    setCart((c) => {
      const ex = c.find((l) => l.menu_item === it.name)
      if (ex) return c.map((l) => l.menu_item === it.name ? { ...l, qty: l.qty + 1 } : l)
      return [...c, { menu_item: it.name, item_name: it.item_name, price: it.price, is_veg: it.is_veg, qty: 1, instructions: "" }]
    })
  const setQty = (mi: string, d: number) =>
    setCart((c) => c.flatMap((l) => l.menu_item === mi ? (l.qty + d <= 0 ? [] : [{ ...l, qty: l.qty + d }]) : [l]))
  const setInstr = (mi: string, v: string) =>
    setCart((c) => c.map((l) => l.menu_item === mi ? { ...l, instructions: v } : l))

  const newSubtotal = cart.reduce((s, l) => s + l.qty * l.price, 0)
  const disc = Math.min(Number(discount) || 0, newSubtotal)

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null)
    try { await fn(); loadOpen() }
    catch (e) { setError(serverError(e)) }
    finally { setBusy(false) }
  }

  const outletName = outlets.find((o) => o.name === outlet)?.outlet_name || outlet
  const orderLabel = (d: { table_no?: string | null; room?: string | null; order_type?: string | null; name?: string }) =>
    d.table_no ? `Table ${d.table_no}`
      : d.room ? `Room ${d.room.split("-").pop()}`
        : d.order_type === "Takeaway" ? "Takeaway" : (d.name || "Order")

  function maybePrintKot(kot: { kot_no: number | null; fired_items: { item_name: string; qty: number; instructions?: string | null }[] },
                         label: string, type: string | null) {
    if (!printKot || !kot.fired_items?.length) return
    printThermal(`KOT #${kot.kot_no}`, kotHtml({
      outlet: outletName, kot_no: kot.kot_no, label,
      order_type: type, order: "", items: kot.fired_items,
    }))
  }

  async function sendNew() {
    await act(async () => {
      const r = await call<{ order: string }>("kamra.pos.create_order", {
        outlet, property: getCurrentProperty(),
        order_type: orderType,
        room: orderType === "Room Service" ? room || null : null,
        table_no: orderType === "Dine In" ? table || null : null,
        items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
      })
      if (disc > 0) await call("kamra.pos.apply_discount", { order: r.order, amount: disc, reason: "" })
      await call("kamra.pos.confirm_order", { order: r.order })
      const kot = await call<{ kot_no: number | null; fired_items: { item_name: string; qty: number; instructions?: string | null }[] }>(
        "kamra.pos.fire_kot", { order: r.order })
      maybePrintKot(kot, orderType === "Dine In" && table ? `Table ${table}`
        : orderType === "Room Service" && room ? `Room ${room.split("-").pop()}` : orderType, orderType)
      newOrder()
    })
  }
  async function addRound() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.add_items", {
        order: selected,
        items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
      })
      const kot = await call<{ kot_no: number | null; fired_items: { item_name: string; qty: number; instructions?: string | null }[] }>(
        "kamra.pos.fire_kot", { order: selected })
      if (detail) maybePrintKot(kot, orderLabel(detail), detail.order_type)
      await reloadDetail(); setCart([])
    })
  }
  async function deliver() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.deliver_order", { order: selected })
      newOrder()
    })
  }
  async function settle(mode: "Cash" | "Card" | "UPI") {
    if (!selected) return
    const order = selected
    await act(async () => {
      await call("kamra.pos.pay_order", { order, mode })
      const bill = await call<BillData>("kamra.pos.bill_data", { order })
      printThermal(`Bill ${order}`, billHtml(bill))
      newOrder()
    })
  }
  async function printBill() {
    if (!selected) return
    const bill = await call<BillData>("kamra.pos.bill_data", { order: selected })
    printThermal(`Bill ${selected}`, billHtml(bill))
  }
  function reprintKot() {
    if (!detail) return
    const items = detail.items.filter((i) => !i.voided && i.kot_status !== "New")
    if (!items.length) return
    printThermal(`KOT #${detail.kot_no}`, kotHtml({
      outlet: outletName, kot_no: detail.kot_no, label: orderLabel(detail),
      order_type: detail.order_type, order: detail.name, reprint: true, items,
    }))
  }
  async function confirmVoid() {
    if (!selected || !voiding || !voidReason.trim()) return
    await act(async () => {
      await call("kamra.pos.void_item", { order: selected, item_row: voiding.row, reason: voidReason })
      setVoiding(null); setVoidReason("")
      await reloadDetail()
    })
  }
  async function confirmCancel() {
    if (!selected || !cancelReason.trim()) return
    await act(async () => {
      await call("kamra.pos.cancel_order", { order: selected, reason: cancelReason })
      newOrder()
    })
  }
  function toggleSplitSel(row: string) {
    setSplitSel((s) => {
      const n = new Set(s)
      if (n.has(row)) n.delete(row); else n.add(row)
      return n
    })
  }
  async function confirmSplit() {
    if (!selected || splitSel.size === 0) return
    const order = selected
    await act(async () => {
      const r = await call<{ new_order: string }>("kamra.pos.split_order", {
        order, item_rows: [...splitSel],
      })
      await openTab(r.new_order) // land on the party's new bill
    })
  }

  function toggleFull() {
    if (document.fullscreenElement) document.exitFullscreen()
    else rootRef.current?.requestFullscreen?.()
  }

  const filtered = query.trim()
    ? cats.flatMap((c) => c.items).filter((it) => it.item_name.toLowerCase().includes(query.toLowerCase()))
    : null

  return (
    <div ref={rootRef} className={full ? "min-h-screen bg-zinc-50 p-4" : ""}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
            <UtensilsCrossed className="size-5 text-brand-600" />Restaurant POS
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-500">
              <input type="checkbox" checked={printKot} onChange={(e) => setPrintKot(e.target.checked)}
                className="accent-brand-600" />
              <Printer className="size-3.5" />Print KOT
            </label>
            <select className={inputCls + " !w-auto"} value={outlet} onChange={(e) => { setOutlet(e.target.value); newOrder() }}>
              {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
            </select>
            <button onClick={toggleFull} className="rounded-lg border border-zinc-300 bg-white p-2 text-zinc-600 hover:bg-zinc-50" title="Full screen">
              {full ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </button>
          </div>
        </div>

        {/* table map - the captain's home view: every table, live state */}
        {tables.length > 0 && (
          <div className="rounded-2xl border border-zinc-200 bg-white p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Tables</h3>
              <div className="flex items-center gap-3 text-[11px] text-zinc-500">
                <span className="flex items-center gap-1"><span className="size-2.5 rounded-full border border-dashed border-zinc-400" />Vacant</span>
                <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-amber-400" />Running</span>
                <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-sky-400" />In kitchen</span>
                <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-emerald-400" />Ready</span>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10">
              {tables.map((t) => (
                <button key={t.table}
                  onClick={() => t.bills === 0 ? newOrder(t.table)
                    : t.bills === 1 ? openTab(t.orders[0].order)
                      : setChooser(chooser === t.table ? null : t.table)}
                  className={"relative rounded-xl border p-2 text-center transition " + TILE[t.state] +
                    (t.orders.some((b) => b.order === selected) || chooser === t.table ? " ring-2 ring-brand-600 ring-offset-1" :
                      t.bills === 0 && selected === null && table === t.table ? " ring-2 ring-brand-600 ring-offset-1" : "")}>
                  {t.bills > 1 && (
                    <span className="absolute -right-1.5 -top-1.5 flex items-center gap-0.5 rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      <Users className="size-2.5" />{t.bills}
                    </span>
                  )}
                  <div className="text-sm font-bold">{t.table}</div>
                  {t.bills > 0 ? (
                    <div className="text-[11px] tabular-nums">₹{inr(t.order_total)}</div>
                  ) : (
                    <div className="text-[11px] opacity-60">+</div>
                  )}
                </button>
              ))}
            </div>
            {chooser && (() => {
              const t = tables.find((x) => x.table === chooser)
              if (!t) return null
              return (
                <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl bg-zinc-50 p-2">
                  <span className="text-xs font-semibold text-zinc-500">{t.table} — {t.bills} bills:</span>
                  {t.orders.map((b) => (
                    <button key={b.order} onClick={() => openTab(b.order)}
                      className={"rounded-lg border px-2.5 py-1 text-sm transition " + TILE[b.state]}>
                      {b.label} <span className="text-xs tabular-nums opacity-70">₹{inr(b.order_total)}</span>
                    </button>
                  ))}
                  <button onClick={() => newOrder(t.table)}
                    className="rounded-lg border border-dashed border-zinc-400 px-2.5 py-1 text-sm text-zinc-600 hover:border-brand-500 hover:text-brand-700">
                    <Plus className="mr-0.5 inline size-3.5" />New bill
                  </button>
                  <button onClick={() => setChooser(null)} className="ml-auto text-zinc-400 hover:text-zinc-600">✕</button>
                </div>
              )
            })()}
          </div>
        )}

        {/* running tabs - step through several tables at once */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => traverse(-1)}
            disabled={open.length === 0}
            aria-label="Previous order"
            className="shrink-0 rounded-lg border border-zinc-300 p-1.5 text-zinc-500 hover:bg-zinc-50 disabled:opacity-40"
          >
            <ChevronLeft className="size-4" />
          </button>
          <div className="flex flex-1 gap-2 overflow-x-auto pb-1">
            <button onClick={() => newOrder()}
              className={"inline-flex shrink-0 items-center gap-1 rounded-lg border px-3 py-1.5 text-sm font-semibold shadow-sm transition " +
                (selected === null
                  ? "border-brand-600 bg-brand-600 text-white"
                  : "border-brand-300 bg-white text-brand-700 hover:border-brand-500 hover:bg-brand-50")}>
              <Plus className="size-4" />New order
            </button>
            {open.map((o) => (
              <button key={o.name} ref={(el) => { if (selected === o.name && el) el.scrollIntoView({ block: "nearest", inline: "nearest" }) }}
                onClick={() => openTab(o.name)}
                className={"inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm " +
                  (selected === o.name ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-zinc-200 bg-white hover:border-brand-400")}>
                {o.label}
                <span className="text-xs text-zinc-400">₹{inr(o.order_total)}</span>
              </button>
            ))}
          </div>
          <button
            onClick={() => traverse(1)}
            disabled={open.length === 0}
            aria-label="Next order"
            className="shrink-0 rounded-lg border border-zinc-300 p-1.5 text-zinc-500 hover:bg-zinc-50 disabled:opacity-40"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

        <div className="grid gap-4 lg:grid-cols-3">
          {/* menu */}
          <div className="lg:col-span-2">
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
              <input className={inputCls + " pl-9"} placeholder="Search the menu…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            {filtered ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {filtered.map((it) => <MenuCard key={it.name} it={it} onAdd={() => addToCart(it)} />)}
                {filtered.length === 0 && <p className="col-span-full py-6 text-center text-sm text-zinc-400">No matches.</p>}
              </div>
            ) : (
              cats.map((c) => (
                <div key={c.category} className="mb-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">{c.category}</h3>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {c.items.map((it) => <MenuCard key={it.name} it={it} onAdd={() => addToCart(it)} />)}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* order panel */}
          <div className="h-fit rounded-2xl border border-zinc-200 bg-white p-4 lg:sticky lg:top-4">
            {selected && detail ? (
              <>
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="flex items-center gap-1.5 font-semibold">
                    {orderLabel(detail)}
                    {detail.table_no && detail.status !== "Delivered" && (
                      <button title="New bill on this table (another party)"
                        onClick={() => newOrder(detail.table_no!)}
                        className="rounded-md border border-dashed border-zinc-300 px-1.5 py-0.5 text-[11px] font-medium text-zinc-500 hover:border-brand-500 hover:text-brand-700">
                        + bill
                      </button>
                    )}
                  </h2>
                  <span className="text-xs text-zinc-400">
                    {detail.kot_no ? `KOT #${detail.kot_no} · ` : ""}{detail.status}
                  </span>
                </div>
                {splitMode && (
                  <p className="mb-1 rounded-lg bg-brand-50 px-2 py-1 text-xs text-brand-700">
                    Tick the lines moving to the new bill.
                  </p>
                )}
                <ul className="mb-2 space-y-1 border-b border-zinc-100 pb-2 text-sm">
                  {detail.items.map((it) => (
                    <li key={it.row} className="group flex items-center justify-between gap-1">
                      <span className={"flex items-center gap-1.5 " + (it.voided ? "text-zinc-400 line-through" : "")}>
                        {splitMode && !it.voided && (
                          <input type="checkbox" className="accent-brand-600"
                            checked={splitSel.has(it.row)} onChange={() => toggleSplitSel(it.row)} />
                        )}
                        <span>
                          {Math.round(it.qty)}× {it.item_name}
                          {!it.voided && it.kot_status !== "New" && <span className="ml-1 text-[10px] text-zinc-400">{it.kot_status}</span>}
                        </span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="tabular-nums">₹{inr(it.amount)}</span>
                        {!splitMode && !it.voided && detail.status !== "Delivered" && (
                          <button title="Void line" onClick={() => { setVoiding(it); setVoidReason("") }}
                            className="text-zinc-300 opacity-0 transition group-hover:opacity-100 hover:text-rose-500">
                            <XCircle className="size-3.5" />
                          </button>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
                {splitMode && (
                  <div className="mb-2 flex gap-1.5">
                    <Button className="flex-1" disabled={busy || splitSel.size === 0 ||
                      splitSel.size >= detail.items.filter((i) => !i.voided).length}
                      onClick={confirmSplit}>
                      <Scissors className="size-4" />Move {splitSel.size || ""} to new bill
                    </Button>
                    <Button variant="ghost" onClick={() => { setSplitMode(false); setSplitSel(new Set()) }}>✕</Button>
                  </div>
                )}
                {voiding && (
                  <div className="mb-2 rounded-lg border border-rose-200 bg-rose-50 p-2">
                    <p className="mb-1 text-xs font-medium text-rose-700">Void {voiding.item_name} — reason required</p>
                    <div className="flex gap-1">
                      <input autoFocus className={inputCls + " !py-1 text-xs"} placeholder="e.g. spilled, wrong item"
                        value={voidReason} onChange={(e) => setVoidReason(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && confirmVoid()} />
                      <Button variant="outline" className="!px-2 !py-1 text-xs font-semibold text-rose-600" disabled={busy || !voidReason.trim()} onClick={confirmVoid}>Void</Button>
                      <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setVoiding(null)}>✕</Button>
                    </div>
                  </div>
                )}
                <div className="mb-2 flex justify-between text-sm font-semibold"><span>Running total</span><span>₹{inr(detail.order_total)}</span></div>
              </>
            ) : (
              <div className="mb-3 space-y-2">
                <div className="flex rounded-lg border border-zinc-200 p-0.5 text-sm">
                  {ORDER_TYPES.map((t) => (
                    <button key={t} onClick={() => setOrderType(t)}
                      className={"flex-1 rounded-md px-2 py-1 " +
                        (orderType === t ? "bg-brand-600 font-medium text-white" : "text-zinc-600 hover:bg-zinc-50")}>
                      {t}
                    </button>
                  ))}
                </div>
                {orderType === "Room Service" && (
                  <select className={inputCls} value={room} onChange={(e) => setRoom(e.target.value)}>
                    <option value="">Room…</option>
                    {rooms.map((r) => <option key={r.name} value={r.name}>Room {r.room_number}</option>)}
                  </select>
                )}
                {orderType === "Dine In" && (
                  tables.length > 0 && !customTable ? (
                    <select className={inputCls} value={table}
                      onChange={(e) => {
                        if (e.target.value === "__custom__") { setCustomTable(true); setTable("") }
                        else setTable(e.target.value)
                      }}>
                      <option value="">Table…</option>
                      {tables.map((t) => (
                        <option key={t.table} value={t.table}>
                          {t.table}{t.bills > 0 ? ` (${t.bills} bill${t.bills > 1 ? "s" : ""} running)` : ""}
                        </option>
                      ))}
                      <option value="__custom__">Temp / custom table…</option>
                    </select>
                  ) : (
                    <div className="flex gap-1.5">
                      <input autoFocus={customTable} className={inputCls} placeholder="Table name (e.g. Patio 2)"
                        value={table} onChange={(e) => setTable(e.target.value)} />
                      {customTable && (
                        <Button variant="ghost" className="!px-2" onClick={() => { setCustomTable(false); setTable("") }}>✕</Button>
                      )}
                    </div>
                  )
                )}
              </div>
            )}

            <h3 className="mb-1 text-sm font-medium text-zinc-500">{selected ? "New round" : "Items"}</h3>
            {cart.length === 0 ? (
              <p className="py-4 text-center text-sm text-zinc-400">Tap items to add.</p>
            ) : (
              <div className="space-y-2">
                {cart.map((l) => (
                  <div key={l.menu_item} className="border-b border-zinc-100 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="flex-1 truncate text-sm font-medium">{l.item_name}</span>
                      <button onClick={() => setQty(l.menu_item, -1)} className="rounded border border-zinc-300 p-0.5"><Minus className="size-3.5" /></button>
                      <span className="w-5 text-center text-sm tabular-nums">{l.qty}</span>
                      <button onClick={() => setQty(l.menu_item, 1)} className="rounded border border-zinc-300 p-0.5"><Plus className="size-3.5" /></button>
                      <span className="w-14 text-right text-sm font-semibold tabular-nums">₹{inr(l.qty * l.price)}</span>
                      <button onClick={() => setQty(l.menu_item, -l.qty)} className="text-zinc-300 hover:text-rose-500"><Trash2 className="size-3.5" /></button>
                    </div>
                    <input className="mt-1 w-full rounded border border-zinc-200 px-2 py-1 text-xs" placeholder="Instructions"
                      value={l.instructions} onChange={(e) => setInstr(l.menu_item, e.target.value)} />
                  </div>
                ))}
              </div>
            )}

            {!selected && cart.length > 0 && (
              <div className="mt-2">
                <input className={inputCls + " !w-28"} placeholder="Discount ₹" inputMode="numeric" value={discount} onChange={(e) => setDiscount(e.target.value)} />
                <div className="mt-2 flex justify-between text-base font-bold"><span>Total</span><span>₹{inr(newSubtotal - disc)}</span></div>
              </div>
            )}

            <div className="mt-3 space-y-2">
              {selected && detail ? (
                <>
                  <Button className="w-full" disabled={busy || cart.length === 0} onClick={addRound}>
                    <Send className="size-4" />Add round & fire KOT
                  </Button>
                  {detail.room ? (
                    <Button variant="outline" className="w-full" disabled={busy} onClick={deliver}>
                      <Wallet className="size-4" />Deliver & post to room
                    </Button>
                  ) : settling ? (
                    <div className="grid grid-cols-3 gap-1.5">
                      {(["Cash", "Card", "UPI"] as const).map((m) => (
                        <Button key={m} variant="outline" disabled={busy} onClick={() => settle(m)}>{m}</Button>
                      ))}
                    </div>
                  ) : (
                    <Button variant="outline" className="w-full" disabled={busy} onClick={() => setSettling(true)}>
                      <Wallet className="size-4" />Settle & print bill
                    </Button>
                  )}
                  <div className="flex gap-1.5">
                    <Button variant="ghost" className="flex-1 !px-2 !py-1 text-xs" disabled={!detail.kot_no} onClick={reprintKot}>
                      <Printer className="size-3.5" />KOT
                    </Button>
                    <Button variant="ghost" className="flex-1 !px-2 !py-1 text-xs" onClick={printBill}>
                      <Receipt className="size-3.5" />Bill
                    </Button>
                    <Button variant="ghost" className="flex-1 !px-2 !py-1 text-xs"
                      disabled={detail.items.filter((i) => !i.voided).length < 2 || detail.status === "Delivered"}
                      onClick={() => { setSplitMode(true); setSplitSel(new Set()) }}>
                      <Scissors className="size-3.5" />Split
                    </Button>
                    <Button variant="ghost" className="flex-1 !px-2 !py-1 text-xs text-rose-600 hover:bg-rose-50"
                      onClick={() => { setCancelling(true); setCancelReason("") }}>
                      <Ban className="size-3.5" />Cancel
                    </Button>
                  </div>
                  {cancelling && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 p-2">
                      <p className="mb-1 text-xs font-medium text-rose-700">Cancel this order — reason required</p>
                      <div className="flex gap-1">
                        <input autoFocus className={inputCls + " !py-1 text-xs"} placeholder="e.g. guest left"
                          value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && confirmCancel()} />
                        <Button variant="outline" className="!px-2 !py-1 text-xs font-semibold text-rose-600" disabled={busy || !cancelReason.trim()} onClick={confirmCancel}>Cancel order</Button>
                        <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setCancelling(false)}>✕</Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <Button className="w-full" disabled={busy || cart.length === 0} onClick={sendNew}>
                  <Send className="size-4" />Send to kitchen
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MenuCard({ it, onAdd }: { it: MenuItem; onAdd: () => void }) {
  return (
    <button onClick={onAdd}
      className="overflow-hidden rounded-xl border border-zinc-200 bg-white text-left transition hover:border-brand-400 hover:shadow-sm">
      {it.image && <img src={it.image} alt="" className="h-20 w-full object-cover" />}
      <div className="p-2.5">
        <div className="flex items-center gap-1">
          <Leaf className={"size-3 " + (it.is_veg ? "text-emerald-600" : "text-rose-500")} />
          <span className="truncate text-sm font-medium">{it.item_name}</span>
        </div>
        <div className="mt-0.5 flex items-center justify-between">
          <span className="text-sm font-semibold text-zinc-700">₹{inr(it.price)}</span>
          <Plus className="size-4 text-brand-600" />
        </div>
      </div>
    </button>
  )
}
