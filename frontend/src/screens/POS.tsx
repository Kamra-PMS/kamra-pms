import { useCallback, useEffect, useRef, useState } from "react"
import {
  Plus, Minus, Trash2, Send, UtensilsCrossed, Leaf, Search,
  Maximize2, Minimize2, Wallet, Printer, Receipt, XCircle, Ban,
  Scissors, Users, MoreHorizontal, PauseCircle, Tag,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { serverError } from "../lib/resource"
import { printThermal, kotHtml, billHtml, type BillData } from "../lib/thermal"
import { Button } from "../components/ui/button"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })
const inr2 = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

interface MenuItem {
  name: string
  item_name: string
  category: string
  price: number
  is_veg: number
  image: string | null
}
interface Outlet { name: string; outlet_name: string; gst_rate: number }
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
  table_no: string | null
}
interface TableBill {
  order: string
  label: string
  order_total: number
  state: "running" | "fired" | "ready"
}
interface TableTile {
  table: string
  seats: number | null
  area: string | null
  temp?: boolean
  state: "vacant" | "running" | "fired" | "ready" | "reserved" | "cleaning"
  bills: number
  order_total?: number
  guests?: number | null
  since?: string
  reservation?: string
  res_guest?: string
  res_party?: number | null
  res_phone?: string | null
  res_time?: string
  orders: TableBill[]
}
interface RecentOrder {
  name: string
  label: string
  status: string
  order_type: string | null
  order_total: number
  paid: number
  payment_mode: string | null
  nc: number
  modified: string
  open: boolean
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
  guests: number | null
  customer_name: string | null
  customer_phone: string | null
  delivery_address: string | null
  nc: number
  nc_authorized_by: string | null
  nc_note: string | null
  paid: number
  payment_mode: string | null
  discount_amount: number
  subtotal: number
  order_total: number
  items: OrderItem[]
}

type OrderType = "Dine In" | "Room Service" | "Takeaway" | "Delivery"
const ORDER_TYPES: OrderType[] = ["Dine In", "Room Service", "Takeaway", "Delivery"]

const TILE: Record<TableTile["state"], string> = {
  vacant: "border-zinc-200 bg-white text-zinc-600 hover:border-brand-400 hover:text-brand-700",
  running: "border-amber-300 bg-amber-50 text-amber-900 hover:border-amber-400",
  fired: "border-sky-300 bg-sky-50 text-sky-900 hover:border-sky-400",
  ready: "border-emerald-300 bg-emerald-50 text-emerald-900 hover:border-emerald-400",
  reserved: "border-violet-300 bg-violet-50 text-violet-900 hover:border-violet-400",
  cleaning: "border-zinc-300 bg-zinc-100 text-zinc-500 hover:border-brand-400",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

/** "23m" / "2h 5m" since a server timestamp. */
function ago(ts?: string) {
  if (!ts) return ""
  const mins = Math.max(0, Math.round((Date.now() - new Date(ts.replace(" ", "T")).getTime()) / 60000))
  if (mins < 60) return `${mins}m`
  if (mins < 600) return `${Math.floor(mins / 60)}h ${mins % 60}m`
  return `${Math.round(mins / 60)}h` // keep long-running tags compact
}

export default function POS() {
  const rootRef = useRef<HTMLDivElement>(null)
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outlet, setOutlet] = useState("")
  const [rooms, setRooms] = useState<{ name: string; room_number: string }[]>([])
  const [cats, setCats] = useState<{ category: string; items: MenuItem[] }[]>([])
  const [cat, setCat] = useState("All")
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState<OpenOrder[]>([])
  const [tables, setTables] = useState<TableTile[]>([])
  const [recent, setRecent] = useState<RecentOrder[]>([])
  const [tableQuery, setTableQuery] = useState("")
  const [tableFilter, setTableFilter] = useState<"all" | "available" | "occupied">("all")
  const [areaFilter, setAreaFilter] = useState("All")
  const [resTile, setResTile] = useState<string | null>(null) // reserved table with panel open
  const [reserveOpen, setReserveOpen] = useState(false)
  const [resForm, setResForm] = useState({ table: "", guest: "", phone: "", party: "", at: "" })
  const [ncOpen, setNcOpen] = useState(false)
  const [ncBy, setNcBy] = useState("Captain")
  const [ncNote, setNcNote] = useState("")
  const [selected, setSelected] = useState<string | null>(null) // null = new bill
  const [detail, setDetail] = useState<Detail | null>(null)
  const [orderType, setOrderType] = useState<OrderType>("Dine In")
  const [room, setRoom] = useState("")
  const [table, setTable] = useState("")
  const [guests, setGuests] = useState("")
  const [custName, setCustName] = useState("")
  const [custPhone, setCustPhone] = useState("")
  const [custAddr, setCustAddr] = useState("")
  const [cart, setCart] = useState<CartLine[]>([]) // new lines (new bill OR next round)
  const [discount, setDiscount] = useState("")
  const [discOpen, setDiscOpen] = useState(false)
  const [printKot, setPrintKot] = useState(() => localStorage.getItem("pos_print_kot") !== "0")
  const [settling, setSettling] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
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
      .then((m) => { setCats(m.categories); setCat("All") })
      .catch((e) => setError(serverError(e)))
  }, [outlet])
  useEffect(loadMenu, [loadMenu])

  const loadOpen = useCallback(() => {
    if (!outlet) return
    call<OpenOrder[]>("kamra.pos.open_orders", { outlet }).then(setOpen).catch(() => {})
    call<{ tables: TableTile[] }>("kamra.pos.table_map", { outlet })
      .then((d) => setTables(d.tables)).catch(() => {})
    call<RecentOrder[]>("kamra.pos.recent_orders", { outlet }).then(setRecent).catch(() => {})
  }, [outlet])
  useEffect(() => {
    loadOpen()
    const unsub = subscribeRealtime(loadOpen) // live tables + bills across captains
    const t = setInterval(loadOpen, 20_000)
    return () => { unsub(); clearInterval(t) }
  }, [loadOpen])

  function resetPanel() {
    setCart([]); setDiscount(""); setDiscOpen(false); setSettling(false); setMoreOpen(false)
    setVoiding(null); setVoidReason(""); setCancelling(false); setCancelReason("")
    setSplitMode(false); setSplitSel(new Set()); setChooser(null)
    setNcOpen(false); setNcBy("Captain"); setNcNote("")
    setResTile(null); setReserveOpen(false)
  }
  function newOrder(atTable?: string) {
    setSelected(null); setDetail(null); setRoom(""); resetPanel()
    setTable(atTable || ""); setCustomTable(false)
    setGuests(""); setCustName(""); setCustPhone(""); setCustAddr("")
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
  /** Cycle open bills (F3); from "new bill" it enters at the first tab. */
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
  const disc = Math.min(Number(discount) || 0, selected ? Number.MAX_SAFE_INTEGER : newSubtotal)

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null)
    try { await fn(); loadOpen() }
    catch (e) { setError(serverError(e)) }
    finally { setBusy(false) }
  }

  const outletDoc = outlets.find((o) => o.name === outlet)
  const outletName = outletDoc?.outlet_name || outlet
  const gstRate = Number(outletDoc?.gst_rate ?? 5)
  const orderLabel = (d: { table_no?: string | null; room?: string | null; order_type?: string | null; customer_name?: string | null; name?: string }) =>
    d.table_no ? `Table ${d.table_no}`
      : d.room ? `Room ${d.room.split("-").pop()}`
        : d.order_type === "Takeaway" || d.order_type === "Delivery"
          ? `${d.order_type}${d.customer_name ? ` · ${d.customer_name.split(" ")[0]}` : ""}`
          : (d.name || "Bill")

  // what the bill panel is pricing right now
  const taxable = selected && detail ? Number(detail.order_total || 0) : newSubtotal - disc
  const gstAmt = taxable * gstRate / 100
  const grand = taxable + gstAmt

  function maybePrintKot(kot: { kot_no: number | null; nc?: boolean; fired_items: { item_name: string; qty: number; instructions?: string | null }[] },
                         label: string, type: string | null,
                         customer?: string | null, address?: string | null,
                         ncBy?: string | null) {
    if (!printKot || !kot.fired_items?.length) return
    printThermal(`KOT #${kot.kot_no}`, kotHtml({
      outlet: outletName, kot_no: kot.kot_no, label,
      order_type: type, order: "", customer, address,
      nc: !!kot.nc, nc_by: ncBy, items: kot.fired_items,
    }))
  }

  function newBillArgs() {
    return {
      outlet, property: getCurrentProperty(),
      order_type: orderType,
      room: orderType === "Room Service" ? room || null : null,
      table_no: orderType === "Dine In" ? table || null : null,
      guests: guests || null,
      customer_name: orderType === "Takeaway" || orderType === "Delivery" ? custName || null : null,
      customer_phone: orderType === "Takeaway" || orderType === "Delivery" ? custPhone || null : null,
      delivery_address: orderType === "Delivery" ? custAddr || null : null,
      items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
    }
  }
  const newBillLabel = () =>
    orderType === "Dine In" && table ? `Table ${table}`
      : orderType === "Room Service" && room ? `Room ${room.split("-").pop()}`
        : `${orderType}${custName ? ` · ${custName.split(" ")[0]}` : ""}`

  /** Create the bill (optionally firing the KOT). Returns the order id. */
  async function createBill(fire: boolean) {
    const r = await call<{ order: string }>("kamra.pos.create_order", newBillArgs())
    if (disc > 0) await call("kamra.pos.apply_discount", { order: r.order, amount: disc, reason: "" })
    await call("kamra.pos.confirm_order", { order: r.order })
    if (fire) {
      const kot = await call<{ kot_no: number | null; fired_items: { item_name: string; qty: number; instructions?: string | null }[] }>(
        "kamra.pos.fire_kot", { order: r.order })
      maybePrintKot(kot, newBillLabel(), orderType,
        custName || null, orderType === "Delivery" ? custAddr || null : null)
    }
    return r.order
  }

  async function kotAction() { // F6 - fire the kitchen ticket
    if (selected) {
      if (cart.length === 0) return
      await act(async () => {
        await call("kamra.pos.add_items", {
          order: selected,
          items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
        })
        const kot = await call<{ kot_no: number | null; nc?: boolean; fired_items: { item_name: string; qty: number; instructions?: string | null }[] }>(
          "kamra.pos.fire_kot", { order: selected })
        if (detail) maybePrintKot(kot, orderLabel(detail), detail.order_type,
          detail.customer_name, detail.delivery_address, detail.nc_authorized_by)
        await reloadDetail(); setCart([])
      })
    } else {
      if (cart.length === 0) return
      await act(async () => { await createBill(true); newOrder() })
    }
  }
  async function hold() { // F5 - park the bill without firing
    if (selected || cart.length === 0) return
    await act(async () => { await createBill(false); newOrder() })
  }
  async function proceedToPay() { // F4
    if (selected && detail) {
      if (detail.room || detail.nc) await act(async () => { await call("kamra.pos.deliver_order", { order: selected }); newOrder() })
      else setSettling(true)
    } else if (cart.length > 0) {
      await act(async () => {
        const order = await createBill(true)
        await openTab(order)
        setSettling(true)
      })
    }
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
      order_type: detail.order_type, order: detail.name, reprint: true,
      customer: detail.customer_name, address: detail.delivery_address,
      nc: !!detail.nc, nc_by: detail.nc_authorized_by, items,
    }))
  }
  async function saveNc(undo = false) {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.mark_nc", {
        order: selected, authorized_by: ncBy, note: ncNote, undo: undo ? 1 : 0,
      })
      setNcOpen(false)
      await reloadDetail()
    })
  }
  async function applyDiscount() {
    if (!selected) { setDiscOpen(false); return } // new bill: applied at create
    await act(async () => {
      await call("kamra.pos.apply_discount", { order: selected, amount: Number(discount) || 0, reason: "" })
      setDiscOpen(false)
      await reloadDetail()
    })
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
  async function saveReservation() {
    const f = resForm
    if (!f.table || !f.guest.trim() || !f.at) return
    await act(async () => {
      await call("kamra.pos.reserve_table", {
        outlet, table_no: f.table, guest_name: f.guest, phone: f.phone || null,
        party_size: f.party || null, reserved_at: f.at.replace("T", " "),
      })
      setReserveOpen(false)
      setResForm({ table: "", guest: "", phone: "", party: "", at: "" })
    })
  }
  async function seatReservation(t: TableTile) {
    if (!t.reservation) return
    await act(async () => {
      await call("kamra.pos.set_reservation", { reservation: t.reservation, status: "Seated" })
      newOrder(t.table)
      if (t.res_party) setGuests(String(t.res_party))
    })
  }
  async function closeReservation(t: TableTile, status: "Cancelled" | "No Show") {
    if (!t.reservation) return
    await act(async () => {
      await call("kamra.pos.set_reservation", { reservation: t.reservation, status })
      setResTile(null)
    })
  }
  async function cleanTable(t: TableTile) {
    await act(async () => {
      await call("kamra.pos.mark_table_clean", { outlet, table_no: t.table })
      newOrder(t.table)
    })
  }

  function toggleFull() {
    if (document.fullscreenElement) document.exitFullscreen()
    else rootRef.current?.requestFullscreen?.()
  }

  // F-key shortcuts (the bar at the bottom is the legend)
  const keysRef = useRef({ newOrder, traverse, proceedToPay, hold, kotAction })
  keysRef.current = { newOrder, traverse, proceedToPay, hold, kotAction }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = keysRef.current
      if (e.key === "F2") { e.preventDefault(); k.newOrder() }
      else if (e.key === "F3") { e.preventDefault(); k.traverse(1) }
      else if (e.key === "F4") { e.preventDefault(); k.proceedToPay() }
      else if (e.key === "F5") { e.preventDefault(); k.hold() }
      else if (e.key === "F6") { e.preventDefault(); k.kotAction() }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const allItems = cats.flatMap((c) => c.items)
  const shownItems = query.trim()
    ? allItems.filter((it) => it.item_name.toLowerCase().includes(query.toLowerCase()))
    : cat === "All" ? null : (cats.find((c) => c.category === cat)?.items || [])

  const tableNames = new Set(tables.map((t) => t.table))
  const looseBills = open.filter((o) =>
    !o.table_no || !tableNames.has(o.table_no))
  const areas = [...new Set(tables.map((t) => t.area).filter(Boolean))] as string[]
  const visibleTables = tables.filter((t) =>
    (tableFilter === "all" || (tableFilter === "available" ? t.state === "vacant" : t.state !== "vacant")) &&
    (areaFilter === "All" || (t.area || "Other") === areaFilter) &&
    (!tableQuery.trim() || t.table.toLowerCase().includes(tableQuery.toLowerCase())))
  const availableCount = tables.filter((t) => t.state === "vacant").length
  // group under area headings when a floor plan has areas and no area is picked
  const tableGroups: [string | null, TableTile[]][] =
    areas.length > 0 && areaFilter === "All"
      ? [...new Map(visibleTables.map((t) => [t.area || "Other", true])).keys()]
          .map((a) => [a, visibleTables.filter((t) => (t.area || "Other") === a)])
      : [[null, visibleTables]]

  const isNewCustomerType = !selected && (orderType === "Takeaway" || orderType === "Delivery")

  return (
    <div ref={rootRef} className={full ? "min-h-screen overflow-y-auto bg-zinc-50 p-4" : ""}>
      <div className="space-y-4">
        {/* header: outlet, order-type tabs, actions */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
            <UtensilsCrossed className="size-5 text-brand-600" />Restaurant POS
            <select className={inputCls + " !w-auto font-normal"} value={outlet} onChange={(e) => { setOutlet(e.target.value); newOrder() }}>
              {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
            </select>
          </h1>
          <div className="flex rounded-xl border border-zinc-200 bg-white p-1 shadow-sm">
            {ORDER_TYPES.map((t) => (
              <button key={t} onClick={() => { setOrderType(t); if (selected) newOrder(); }}
                className={"rounded-lg px-3 py-1.5 text-sm transition " +
                  ((selected && detail ? detail.order_type : orderType) === t
                    ? "bg-brand-600 font-semibold text-white"
                    : "text-zinc-600 hover:bg-zinc-50")}>
                {t}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-500">
              <input type="checkbox" checked={printKot} onChange={(e) => setPrintKot(e.target.checked)}
                className="accent-brand-600" />
              <Printer className="size-3.5" />Print KOT
            </label>
            <button onClick={toggleFull} className="rounded-lg border border-zinc-300 bg-white p-2 text-zinc-600 hover:bg-zinc-50" title="Full screen">
              {full ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </button>
            <Button onClick={() => newOrder()}>
              <Plus className="size-4" />New Bill
              <kbd className="rounded bg-white/20 px-1 text-[10px]">F2</kbd>
            </Button>
          </div>
        </div>
        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

        <div className="grid gap-4 lg:grid-cols-12">
          {/* ── left: tables + recent ── */}
          <div className="space-y-4 lg:col-span-3">
            <div className="rounded-2xl border border-zinc-200 bg-white p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-bold text-zinc-800">Tables</h3>
                {tables.length > 0 && (
                  <button onClick={() => setReserveOpen((v) => !v)}
                    className="rounded-lg border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-600 hover:border-violet-400 hover:text-violet-700">
                    + Reserve
                  </button>
                )}
              </div>
              {reserveOpen && (
                <div className="mb-2 space-y-1.5 rounded-xl border border-violet-200 bg-violet-50 p-2">
                  <div className="grid grid-cols-2 gap-1.5">
                    <select className={inputCls + " !py-1 text-xs"} value={resForm.table}
                      onChange={(e) => setResForm({ ...resForm, table: e.target.value })}>
                      <option value="">Table…</option>
                      {tables.filter((t) => !t.temp).map((t) => <option key={t.table} value={t.table}>{t.table}</option>)}
                    </select>
                    <input className={inputCls + " !py-1 text-xs"} type="datetime-local" value={resForm.at}
                      onChange={(e) => setResForm({ ...resForm, at: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <input className={inputCls + " !py-1 text-xs"} placeholder="Guest name" value={resForm.guest}
                      onChange={(e) => setResForm({ ...resForm, guest: e.target.value })} />
                    <input className={inputCls + " !py-1 text-xs"} placeholder="Phone" value={resForm.phone}
                      onChange={(e) => setResForm({ ...resForm, phone: e.target.value })} />
                  </div>
                  <div className="flex gap-1.5">
                    <input className={inputCls + " !w-20 !py-1 text-xs"} placeholder="Party" inputMode="numeric" value={resForm.party}
                      onChange={(e) => setResForm({ ...resForm, party: e.target.value.replace(/\D/g, "") })} />
                    <Button className="flex-1 !py-1 text-xs" disabled={busy || !resForm.table || !resForm.guest.trim() || !resForm.at}
                      onClick={saveReservation}>Reserve</Button>
                    <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setReserveOpen(false)}>✕</Button>
                  </div>
                </div>
              )}
              {tables.length > 0 ? (
                <>
                  <div className="relative mb-2">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
                    <input className={inputCls + " !py-1 pl-8 text-xs"} placeholder="Search table…"
                      value={tableQuery} onChange={(e) => setTableQuery(e.target.value)} />
                  </div>
                  <div className="mb-1 flex flex-wrap gap-1">
                    {([["all", `All (${tables.length})`], ["available", `Available (${availableCount})`],
                       ["occupied", `Occupied (${tables.length - availableCount})`]] as const).map(([k, l]) => (
                      <button key={k} onClick={() => setTableFilter(k)}
                        className={"rounded-full px-2 py-0.5 text-[11px] font-medium " +
                          (tableFilter === k ? "bg-brand-600 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200")}>
                        {l}
                      </button>
                    ))}
                  </div>
                  {areas.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-1">
                      {["All", ...areas].map((a) => (
                        <button key={a} onClick={() => setAreaFilter(a)}
                          className={"rounded-full px-2 py-0.5 text-[11px] " +
                            (areaFilter === a ? "bg-zinc-800 font-medium text-white" : "bg-white text-zinc-500 ring-1 ring-zinc-200 hover:ring-zinc-400")}>
                          {a}
                        </button>
                      ))}
                    </div>
                  )}
                  {tableGroups.map(([groupName, group]) => (
                    <div key={groupName ?? "_"} className="mb-2">
                      {groupName && (
                        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{groupName}</h4>
                      )}
                      <div className="grid grid-cols-3 gap-2">
                        {group.map((t) => (
                          <button key={t.table}
                            onClick={() => t.state === "reserved" ? setResTile(resTile === t.table ? null : t.table)
                              : t.state === "cleaning" ? cleanTable(t)
                                : t.bills === 0 ? newOrder(t.table)
                                  : t.bills === 1 ? openTab(t.orders[0].order)
                                    : setChooser(chooser === t.table ? null : t.table)}
                            className={"relative rounded-xl border p-2 text-left transition " + TILE[t.state] +
                              (t.temp ? " border-dashed" : "") +
                              (t.orders.some((b) => b.order === selected) || chooser === t.table ? " ring-2 ring-brand-600 ring-offset-1" :
                                t.bills === 0 && selected === null && table === t.table ? " ring-2 ring-brand-600 ring-offset-1" : "")}>
                            {t.bills > 1 && (
                              <span className="absolute -right-1.5 -top-1.5 flex items-center gap-0.5 rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                                <Users className="size-2.5" />{t.bills}
                              </span>
                            )}
                            <div className="flex items-baseline justify-between gap-1">
                              <span className="truncate text-sm font-bold">{t.table}</span>
                              {t.bills > 0 && t.since && (
                                <span className="shrink-0 text-[9px] font-medium opacity-60">{ago(t.since)}</span>
                              )}
                            </div>
                            <div className="truncate text-[10px] opacity-70">
                              {t.bills > 0
                                ? <>₹{inr(t.order_total)}{t.guests ? <> · <Users className="inline size-2.5" />{t.guests}</> : null}</>
                                : t.state === "reserved" ? `Res ${t.res_time} · ${t.res_guest || ""}`
                                  : t.state === "cleaning" ? "Cleaning"
                                    : t.seats ? `${t.seats} seats` : " "}
                            </div>
                          </button>
                        ))}
                        {groupName === null && visibleTables.length === 0 && (
                          <p className="col-span-3 py-3 text-center text-xs text-zinc-400">No tables match.</p>
                        )}
                      </div>
                    </div>
                  ))}
                  {resTile && (() => {
                    const t = tables.find((x) => x.table === resTile)
                    if (!t || t.state !== "reserved") return null
                    return (
                      <div className="mb-2 space-y-1.5 rounded-xl border border-violet-200 bg-violet-50 p-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-violet-900">
                            {t.table} · {t.res_time} · {t.res_guest}
                            {t.res_party ? ` · ${t.res_party} pax` : ""}
                          </span>
                          <button onClick={() => setResTile(null)} className="text-violet-400 hover:text-violet-700">✕</button>
                        </div>
                        {t.res_phone && <p className="text-[11px] text-violet-700">{t.res_phone}</p>}
                        <div className="flex gap-1.5">
                          <Button className="flex-1 !py-1 text-xs" disabled={busy} onClick={() => seatReservation(t)}>Seat now</Button>
                          <Button variant="outline" className="!px-2 !py-1 text-xs" disabled={busy} onClick={() => closeReservation(t, "No Show")}>No show</Button>
                          <Button variant="outline" className="!px-2 !py-1 text-xs text-rose-600" disabled={busy} onClick={() => closeReservation(t, "Cancelled")}>Cancel</Button>
                        </div>
                      </div>
                    )
                  })()}
                  <button onClick={() => { newOrder(); setOrderType("Dine In"); setCustomTable(true) }}
                    className="w-full rounded-xl border border-dashed border-zinc-300 px-2 py-1.5 text-xs font-medium text-zinc-500 transition hover:border-brand-500 hover:text-brand-700">
                    <Plus className="mr-0.5 inline size-3.5" />Temp table
                  </button>
                  {chooser && (() => {
                    const t = tables.find((x) => x.table === chooser)
                    if (!t) return null
                    return (
                      <div className="mt-2 space-y-1 rounded-xl bg-zinc-50 p-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-zinc-500">{t.table} — {t.bills} bills</span>
                          <button onClick={() => setChooser(null)} className="text-zinc-400 hover:text-zinc-600">✕</button>
                        </div>
                        {t.orders.map((b) => (
                          <button key={b.order} onClick={() => openTab(b.order)}
                            className={"flex w-full items-center justify-between rounded-lg border px-2 py-1 text-xs transition " + TILE[b.state]}>
                            <span>{b.label}</span><span className="tabular-nums">₹{inr(b.order_total)}</span>
                          </button>
                        ))}
                        <button onClick={() => newOrder(t.table)}
                          className="w-full rounded-lg border border-dashed border-zinc-400 px-2 py-1 text-xs text-zinc-600 hover:border-brand-500 hover:text-brand-700">
                          <Plus className="mr-0.5 inline size-3" />New bill
                        </button>
                      </div>
                    )
                  })()}
                </>
              ) : (
                <p className="py-2 text-xs text-zinc-400">
                  No table layout for this outlet yet — add tables (one per line,
                  <code className="mx-1 rounded bg-zinc-100 px-1">T1:4</code> = 4 seats) on the POS Outlet.
                </p>
              )}
              {looseBills.length > 0 && (
                <div className="mt-3 border-t border-zinc-100 pt-2">
                  <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">Rooms · takeaway · delivery</h4>
                  <div className="flex flex-wrap gap-1">
                    {looseBills.map((o) => (
                      <button key={o.name} onClick={() => openTab(o.name)}
                        className={"rounded-lg border px-2 py-1 text-xs transition " +
                          (selected === o.name ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-zinc-200 bg-white hover:border-brand-400")}>
                        {o.label} <span className="tabular-nums text-zinc-400">₹{inr(o.order_total)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-zinc-200 bg-white p-3">
              <h3 className="mb-2 text-sm font-bold text-zinc-800">Recent orders</h3>
              <ul className="space-y-1">
                {recent.map((r) => (
                  <li key={r.name}>
                    <button disabled={!r.open} onClick={() => openTab(r.name)}
                      className={"flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs " +
                        (r.open ? "hover:bg-brand-50" : "cursor-default opacity-60")}>
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{r.label}</span>
                        <span className="ml-1 text-zinc-400">· {r.order_type}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5 tabular-nums">
                        <span className="font-semibold">₹{inr(r.order_total)}</span>
                        {r.nc ? <span className="rounded bg-amber-50 px-1 text-[10px] font-bold text-amber-700">NC</span>
                          : r.paid ? <span className="rounded bg-emerald-50 px-1 text-[10px] font-medium text-emerald-700">{r.payment_mode}</span>
                            : r.status === "Cancelled" ? <span className="rounded bg-rose-50 px-1 text-[10px] font-medium text-rose-600">✕</span>
                              : null}
                        <span className="text-zinc-400">{ago(r.modified)}</span>
                      </span>
                    </button>
                  </li>
                ))}
                {recent.length === 0 && <p className="py-2 text-center text-xs text-zinc-400">No orders yet today.</p>}
              </ul>
            </div>
          </div>

          {/* ── centre: menu ── */}
          <div className="lg:col-span-5">
            <div className="relative mb-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
              <input className={inputCls + " pl-9"} placeholder="Search menu items…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <div className="mb-3 flex gap-1.5 overflow-x-auto pb-1">
              {["All", ...cats.map((c) => c.category)].map((c) => (
                <button key={c} onClick={() => { setCat(c); setQuery("") }}
                  className={"shrink-0 rounded-full px-3 py-1 text-sm font-medium transition " +
                    (cat === c && !query.trim() ? "bg-brand-600 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200 hover:ring-brand-400")}>
                  {c}
                </button>
              ))}
            </div>
            {shownItems ? (
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
                {shownItems.map((it) => <MenuCard key={it.name} it={it} onAdd={() => addToCart(it)} />)}
                {shownItems.length === 0 && <p className="col-span-full py-6 text-center text-sm text-zinc-400">No matches.</p>}
              </div>
            ) : (
              cats.map((c) => (
                <div key={c.category} className="mb-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">{c.category}</h3>
                  <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
                    {c.items.map((it) => <MenuCard key={it.name} it={it} onAdd={() => addToCart(it)} />)}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* ── right: the bill ── */}
          <div className="h-fit rounded-2xl border border-zinc-200 bg-white p-4 lg:sticky lg:top-4 lg:col-span-4">
            {/* who / where */}
            {selected && detail ? (
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-1.5 font-semibold">
                  {orderLabel(detail)}
                  {detail.guests ? <span className="flex items-center gap-0.5 text-xs font-normal text-zinc-400"><Users className="size-3" />{detail.guests}</span> : null}
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
            ) : (
              <div className="mb-3 space-y-2">
                {orderType === "Dine In" && (
                  <div className="grid grid-cols-2 gap-2">
                    {tables.length > 0 && !customTable ? (
                      <select className={inputCls} value={table}
                        onChange={(e) => {
                          if (e.target.value === "__custom__") { setCustomTable(true); setTable("") }
                          else setTable(e.target.value)
                        }}>
                        <option value="">Table…</option>
                        {tables.map((t) => (
                          <option key={t.table} value={t.table}>
                            {t.table}{t.seats ? ` (${t.seats})` : ""}{t.bills > 0 ? ` · ${t.bills} bill${t.bills > 1 ? "s" : ""}` : ""}
                          </option>
                        ))}
                        <option value="__custom__">Temp / custom table…</option>
                      </select>
                    ) : (
                      <div className="flex gap-1">
                        <input autoFocus={customTable} className={inputCls} placeholder="Table name"
                          value={table} onChange={(e) => setTable(e.target.value)} />
                        {customTable && (
                          <Button variant="ghost" className="!px-2" onClick={() => { setCustomTable(false); setTable("") }}>✕</Button>
                        )}
                      </div>
                    )}
                    <div className="flex items-center gap-1 rounded-lg border border-zinc-300 px-2">
                      <Users className="size-3.5 text-zinc-400" />
                      <input className="w-full bg-transparent py-1.5 text-sm focus:outline-none" placeholder="Guests"
                        inputMode="numeric" value={guests} onChange={(e) => setGuests(e.target.value.replace(/\D/g, ""))} />
                    </div>
                  </div>
                )}
                {orderType === "Room Service" && (
                  <select className={inputCls} value={room} onChange={(e) => setRoom(e.target.value)}>
                    <option value="">Room…</option>
                    {rooms.map((r) => <option key={r.name} value={r.name}>Room {r.room_number}</option>)}
                  </select>
                )}
                {isNewCustomerType && (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <input className={inputCls} placeholder="Customer name" value={custName} onChange={(e) => setCustName(e.target.value)} />
                      <input className={inputCls} placeholder="Phone" value={custPhone} onChange={(e) => setCustPhone(e.target.value)} />
                    </div>
                    {orderType === "Delivery" && (
                      <input className={inputCls} placeholder="Delivery address" value={custAddr} onChange={(e) => setCustAddr(e.target.value)} />
                    )}
                  </>
                )}
              </div>
            )}

            {/* items */}
            <div className="mb-1 flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-500">{selected ? "Order items" : "Order items"}</h3>
              {!selected && cart.length > 0 && (
                <button onClick={() => setCart([])} className="text-xs text-zinc-400 hover:text-rose-500">Clear all</button>
              )}
            </div>

            {selected && detail && (
              <>
                {!!detail.nc && (
                  <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                    <span className="font-bold">NC — COMPLIMENTARY</span>
                    <span className="ml-1">auth: {detail.nc_authorized_by}{detail.nc_note ? ` · ${detail.nc_note}` : ""}</span>
                  </div>
                )}
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
                {cart.length > 0 && <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">New round</h4>}
              </>
            )}

            {cart.length === 0 && !(selected && detail) ? (
              <p className="py-4 text-center text-sm text-zinc-400">Tap menu items to add.</p>
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

            {/* money */}
            <div className="mt-3 space-y-1 border-t border-zinc-100 pt-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">Discount</span>
                {discOpen ? (
                  <span className="flex items-center gap-1">
                    <input autoFocus className={inputCls + " !w-24 !py-0.5 text-xs"} placeholder="₹" inputMode="numeric"
                      value={discount} onChange={(e) => setDiscount(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && applyDiscount()} />
                    <Button variant="outline" className="!px-2 !py-0.5 text-xs" disabled={busy} onClick={applyDiscount}>OK</Button>
                  </span>
                ) : (
                  <button onClick={() => setDiscOpen(true)} className="flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                    <Tag className="size-3" />
                    {(selected && detail ? detail.discount_amount : disc) > 0
                      ? `−₹${inr(selected && detail ? detail.discount_amount : disc)}`
                      : "Add discount"}
                  </button>
                )}
              </div>
              <div className="flex justify-between text-zinc-500"><span>Subtotal</span><span className="tabular-nums">₹{inr2(taxable)}</span></div>
              <div className="flex justify-between text-xs text-zinc-400"><span>CGST ({gstRate / 2}%)</span><span className="tabular-nums">₹{inr2(gstAmt / 2)}</span></div>
              <div className="flex justify-between text-xs text-zinc-400"><span>SGST ({gstRate / 2}%)</span><span className="tabular-nums">₹{inr2(gstAmt / 2)}</span></div>
              <div className="flex justify-between text-base font-bold"><span>Total</span><span className="tabular-nums">₹{inr2(grand)}</span></div>
            </div>

            {ncOpen && selected && (
              <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2">
                <p className="mb-1 text-xs font-medium text-amber-800">Mark NC (no charge) — who authorized it?</p>
                <div className="flex gap-1">
                  <select className={inputCls + " !w-28 !py-1 text-xs"} value={ncBy} onChange={(e) => setNcBy(e.target.value)}>
                    {["Captain", "Chef", "Manager", "GM", "Management", "Owner"].map((w) => <option key={w}>{w}</option>)}
                  </select>
                  <input autoFocus className={inputCls + " !py-1 text-xs"} placeholder="Reference (birthday, complaint #, promo…)"
                    value={ncNote} onChange={(e) => setNcNote(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveNc()} />
                  <Button variant="outline" className="!px-2 !py-1 text-xs font-semibold text-amber-700" disabled={busy} onClick={() => saveNc()}>NC</Button>
                  <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setNcOpen(false)}>✕</Button>
                </div>
              </div>
            )}

            {cancelling && (
              <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-2">
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

            {/* actions */}
            <div className="mt-3 space-y-2">
              <div className="flex gap-1.5">
                <Button variant="outline" className="flex-1 !px-2 text-xs" disabled={busy || !!selected || cart.length === 0} onClick={hold}>
                  <PauseCircle className="size-3.5" />Hold
                </Button>
                <Button variant="outline" className="flex-1 !px-2 text-xs"
                  disabled={busy || !selected || !detail || detail.items.filter((i) => !i.voided).length < 2 || detail.status === "Delivered"}
                  onClick={() => { setSplitMode(true); setSplitSel(new Set()) }}>
                  <Scissors className="size-3.5" />Split bill
                </Button>
                <div className="relative flex-1">
                  <Button variant="outline" className="w-full !px-2 text-xs" disabled={busy || !selected} onClick={() => setMoreOpen((v) => !v)}>
                    <MoreHorizontal className="size-3.5" />More
                  </Button>
                  {moreOpen && selected && detail && (
                    <div className="absolute bottom-full right-0 z-10 mb-1 w-40 rounded-xl border border-zinc-200 bg-white p-1 shadow-lg">
                      <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-zinc-50"
                        onClick={() => { setMoreOpen(false); reprintKot() }} disabled={!detail.kot_no}>
                        <Printer className="size-3.5" />Reprint KOT
                      </button>
                      <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-zinc-50"
                        onClick={() => { setMoreOpen(false); printBill() }}>
                        <Receipt className="size-3.5" />Print bill
                      </button>
                      {detail.status !== "Delivered" && (
                        detail.nc ? (
                          <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-amber-700 hover:bg-amber-50"
                            onClick={() => { setMoreOpen(false); saveNc(true) }}>
                            <Tag className="size-3.5" />Remove NC
                          </button>
                        ) : (
                          <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-amber-700 hover:bg-amber-50"
                            onClick={() => { setMoreOpen(false); setNcOpen(true) }}>
                            <Tag className="size-3.5" />Mark NC (comp)
                          </button>
                        )
                      )}
                      <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-rose-600 hover:bg-rose-50"
                        onClick={() => { setMoreOpen(false); setCancelling(true); setCancelReason("") }}>
                        <Ban className="size-3.5" />Cancel order
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <Button variant="outline" className="w-full"
                disabled={busy || cart.length === 0}
                onClick={kotAction}>
                <Send className="size-4" />{selected ? "Add round & fire KOT" : "Send to kitchen"}
                <kbd className="rounded bg-zinc-100 px-1 text-[10px] text-zinc-500">F6</kbd>
              </Button>
              {settling ? (
                <div className="grid grid-cols-3 gap-1.5">
                  {(["Cash", "Card", "UPI"] as const).map((m) => (
                    <Button key={m} disabled={busy} onClick={() => settle(m)}>{m}</Button>
                  ))}
                </div>
              ) : (
                <Button className="w-full"
                  disabled={busy || (selected ? !detail : cart.length === 0)}
                  onClick={proceedToPay}>
                  <Wallet className="size-4" />
                  {selected && detail?.nc ? "Close NC bill"
                    : selected && detail?.room ? "Deliver & post to room" : "Proceed to pay"}
                  <kbd className="rounded bg-white/20 px-1 text-[10px]">F4</kbd>
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* shortcut legend */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-xl border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-500">
          {([["F2", "New bill"], ["F3", "Cycle open bills"], ["F4", "Proceed to pay"],
             ["F5", "Hold bill"], ["F6", "Fire KOT"]] as const).map(([k, l]) => (
            <span key={k} className="flex items-center gap-1.5">
              <kbd className="rounded border border-zinc-300 bg-zinc-50 px-1.5 py-0.5 font-semibold text-zinc-600">{k}</kbd>{l}
            </span>
          ))}
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
