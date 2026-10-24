import { useCallback, useEffect, useRef, useState } from "react"
import {
  Plus, Minus, Trash2, Send, UtensilsCrossed, Search,
  Maximize2, Minimize2, Wallet, Printer, Receipt, XCircle, Ban,
  Scissors, Users, PauseCircle, Tag, Gift, Menu, LogOut, Focus,
  Keyboard, LayoutGrid, BedDouble, ListOrdered, UserRound, MoreVertical, History,
} from "lucide-react"
import PosSidePanel from "./pos/PosSidePanel"
import SettleSheet from "./pos/SettleSheet"
import OpenBillsPopup from "./pos/OpenBillsPopup"
import OrderHistory from "./pos/OrderHistory"
import VoidApproval, { type VoidArgs } from "./pos/VoidApproval"
import { useNavigate } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { printThermal, kotHtml, billHtml, PRINT_DIALOG_EVENT, type BillData, type KotLine } from "../lib/thermal"
import { useFloorFullscreen } from "../lib/kiosk"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"


const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })
const inr2 = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })

interface MenuItem {
  name: string
  item_name: string
  category: string
  price: number
  is_veg: number
  image: string | null
}
interface Outlet {
  name: string
  outlet_name: string
  gst_rate: number
  auto_kot?: 0 | 1
}
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
  creation: string
  nc?: number
  /** minutes since the bill was opened */
  age_min?: number
  /** nothing sent to the kitchen for longer than the F&B setting allows */
  stale?: 0 | 1
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
interface KotTicket {
  kot_no: number | null
  at?: string
  round?: number
  nc?: boolean
  nc_by?: string | null
  label: string
  order_type?: string | null
  order: string
  customer?: string | null
  address?: string | null
  items: KotLine[]
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
  kot_tickets: KotTicket[]
  paid: number
  payment_mode: string | null
  discount_amount: number
  subtotal: number
  order_total: number
  items: OrderItem[]
  guest?: string | null
  reservation?: string | null
  allergy_note?: string | null
  /** live lines the kitchen already has: 0 = the captain cancels alone */
  kitchen_lines?: number
  /** the signed-in user may approve voids of food the kitchen has */
  can_approve?: 0 | 1
}

type OrderType = "Dine In" | "Room Service" | "Takeaway" | "Delivery"
const ORDER_TYPES: OrderType[] = ["Dine In", "Room Service", "Takeaway", "Delivery"]
/** A room with a checked-in guest - the only kind that can take a room charge. */
interface InHouseRoom {
  room: string; room_number: string; guest_name: string | null; reservation: string
  /** the check-in's decision; a blocked room cannot take a room charge */
  room_charges_allowed?: 0 | 1
  check_out_date?: string
}

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

const OUTLET_KEY = "kamra_pos_outlet"

export default function POS() {
  const { t } = useT()
  const { ensureUnlocked } = useCashierAuth()
  // pay_order settles Cash / Card / UPI; offer the ones this country uses
  const loc = useLocale()
  const posModes = ["Cash", "Card", "UPI"].filter((m) => loc.payment_modes.includes(m))
  const rootRef = useRef<HTMLDivElement>(null)
  const [outlets, setOutlets] = useState<Outlet[]>([])
  const [outlet, setOutlet] = useState("")
  const [rooms, setRooms] = useState<InHouseRoom[]>([])
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
  const [postRoom, setPostRoom] = useState("") // settle sheet: charge a running bill to a room
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
  const [sheetNc, setSheetNc] = useState(false) // NC tender open inside the settle sheet
  const [voiding, setVoiding] = useState<OrderItem | null>(null)
  const [cancelling, setCancelling] = useState(false)
  // the side panel (orders list / who the bill is for) and its live refresh
  const [panel, setPanel] = useState<"orders" | "guest" | null>(null)
  const [panelKey, setPanelKey] = useState(0)
  const [historyOpen, setHistoryOpen] = useState(false)
  // a customer chosen for a bill not created yet
  const [draftGuest, setDraftGuest] = useState<{ guest: string; full_name: string } | null>(null)
  const [chooser, setChooser] = useState<string | null>(null) // table with several bills
  const [splitMode, setSplitMode] = useState(false)
  const [splitSel, setSplitSel] = useState<Set<string>>(new Set())
  const [customTable, setCustomTable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [printNote, setPrintNote] = useState<string | null>(null)
  // A KOT that waited on the browser's print dialog: tell this till, once,
  // how to print silently.
  const [printTip, setPrintTip] = useState(false)
  useEffect(() => {
    const KEY = "kamra_print_tip_seen"
    const onDialog = () => {
      try { if (localStorage.getItem(KEY)) return; localStorage.setItem(KEY, "1") } catch { /* private mode */ }
      setPrintTip(true)
    }
    window.addEventListener(PRINT_DIALOG_EVENT, onDialog)
    return () => window.removeEventListener(PRINT_DIALOG_EVENT, onDialog)
  }, [])
  // responsive chrome: which pane a phone shows, the tablet tables drawer,
  // header overflow, and bill-actions menu
  const [mobilePane, setMobilePane] = useState<"tables" | "menu" | "bill">("menu")
  const [tablesOpen, setTablesOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [billMenuOpen, setBillMenuOpen] = useState(false)
  const [billsPopupOpen, setBillsPopupOpen] = useState(false)
  const navigate = useNavigate()
  const { floorOn, kioskOn, browserFs, toggleBrowserFs, toggleFocus, exitFloor } =
    useFloorFullscreen(rootRef)

  useEffect(() => {
    call<Outlet[]>("kamra.pos.outlets", { property: getCurrentProperty() })
      .then((o) => {
        setOutlets(o)
        // a till belongs to one outlet: reopen on the one it used last, and
        // never override a choice made while the list was loading
        let saved = ""
        try { saved = localStorage.getItem(OUTLET_KEY) || "" } catch { /* private mode */ }
        setOutlet((cur) => o.some((x) => x.name === cur) ? cur
          : o.some((x) => x.name === saved) ? saved : (o[0]?.name ?? ""))
      })
      .catch((e) => setError(serverError(e)))
    loadRooms()
  }, [])

  /** Only rooms with a checked-in guest can take a room charge. */
  function loadRooms() {
    call<InHouseRoom[]>("kamra.pos.in_house_rooms", { property: getCurrentProperty() })
      .then((d) => setRooms(d || []))
      .catch(() => {})
  }

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
    setPanelKey((k) => k + 1)
  }, [outlet])
  useEffect(() => {
    loadOpen()
    // live tables + bills across captains; the front desk's traffic is ignored
    const unsub = subscribeRealtime(loadOpen, {
      filter: (e) => e.doctype === "POS Order" && (!e.outlet || e.outlet === outlet),
      fallbackMs: 5000,
    })
    const t = setInterval(loadOpen, 20_000)
    return () => { unsub(); clearInterval(t) }
  }, [loadOpen, outlet])

  function resetPanel() {
    setCart([]); setDiscount(""); setDiscOpen(false); setSettling(false); setSheetNc(false)
    setVoiding(null); setCancelling(false)
    setSplitMode(false); setSplitSel(new Set()); setChooser(null)
    setNcOpen(false); setNcBy("Captain"); setNcNote("")
    setResTile(null); setReserveOpen(false); setTablesOpen(false)
  }
  function newOrder(atTable?: string) {
    setSelected(null); setDetail(null); setRoom(""); setPostRoom(""); resetPanel()
    setTable(atTable || ""); setCustomTable(false)
    setGuests(""); setCustName(""); setCustPhone(""); setCustAddr("")
    setDraftGuest(null)
    if (atTable) setOrderType("Dine In")
    setTablesOpen(false)
    setMobilePane("menu") // a fresh bill starts at the menu on a phone
  }
  /** Cart / draft table pick - same rules as the Tables drawer. */
  function pickCartTable(value: string) {
    if (value === "__custom__") {
      setCustomTable(true)
      setTable("")
      setChooser(null)
      return
    }
    if (!value) {
      setTable("")
      setChooser(null)
      return
    }
    const tile = tables.find((x) => x.table === value)
    if (!tile || tile.bills === 0) {
      setTable(value)
      setChooser(null)
      return
    }
    if (tile.bills === 1) {
      setChooser(null)
      void openTab(tile.orders[0].order)
      return
    }
    setTable(value)
    setChooser(value)
  }
  async function openTab(name: string, opts?: { popup?: boolean }) {
    setSelected(name); resetPanel()
    setTablesOpen(false)
    setMobilePane("bill") // an existing bill opens on the bill on a phone
    if (opts?.popup) setBillsPopupOpen(true)
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

  const addToCart = (it: MenuItem) => {
    setCart((c) => {
      const ex = c.find((l) => l.menu_item === it.name)
      // bump qty and move that line to the top so the add is never buried
      if (ex) {
        const next = c.map((l) => l.menu_item === it.name ? { ...l, qty: l.qty + 1 } : l)
        const line = next.find((l) => l.menu_item === it.name)!
        return [line, ...next.filter((l) => l.menu_item !== it.name)]
      }
      return [{
        menu_item: it.name, item_name: it.item_name, price: it.price,
        is_veg: it.is_veg, qty: 1, instructions: "",
      }, ...c]
    })
  }
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
  // Outlet setting wins over the till's own printer switch: punch, print, KDS.
  const autoKot = Number(outletDoc?.auto_kot) === 1
  const willPrintKot = autoKot || printKot
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

  function printSavedKot(t: KotTicket, reprint = false) {
    printThermal(`KOT #${t.kot_no}`, kotHtml({
      outlet: outletName, kot_no: t.kot_no, label: t.label,
      order_type: t.order_type, order: t.order, reprint,
      customer: t.customer, address: t.address,
      nc: !!t.nc, nc_by: t.nc_by, items: t.items,
    }))
  }

  function maybePrintKot(kot: {
    kot_no: number | null
    nc?: boolean
    ticket?: KotTicket
    till_ticket?: KotTicket
    print_jobs?: { printer_name: string }[]
    fired_items: { item_name: string; qty: number; instructions?: string | null }[]
  }, label: string, type: string | null,
                         customer?: string | null, address?: string | null,
                         ncBy?: string | null) {
    const full = kot.ticket ?? {
      kot_no: kot.kot_no, label, order_type: type, order: "",
      customer, address, nc: !!kot.nc, nc_by: ncBy, items: kot.fired_items,
    }
    if (!full.items?.length) return
    const kotNo = full.kot_no ?? "-"
    // Kitchen printers took the lines they serve; this till prints the rest.
    const sentTo = [...new Set((kot.print_jobs ?? []).map((j) => j.printer_name))]
    const mine = kot.till_ticket ?? full
    const notes: string[] = []
    if (sentTo.length) {
      notes.push(t("KOT {kot} sent to {printers}.", { kot: kotNo, printers: sentTo.join(", ") }))
    }
    if (mine.items.length) {
      notes.push(willPrintKot
        ? (sentTo.length
          ? t("The rest printed here.")
          : t("KOT {kot} printed and on the kitchen display.", { kot: kotNo }))
        : (sentTo.length
          ? t("Some items have no kitchen printer; turn on Print KOT to print them here.")
          : t("KOT {kot} is on the kitchen display. Turn on Print KOT to send it to the printer.", { kot: kotNo })))
    }
    setPrintNote(notes.join(" "))
    if (!willPrintKot || !mine.items.length) return
    printSavedKot(mine)
  }

  function newBillArgs() {
    return {
      outlet, property: getCurrentProperty(),
      order_type: orderType,
      // room service, or a dine-in guest charging the bill to their room
      room: orderType === "Room Service" || orderType === "Dine In" ? room || null : null,
      table_no: orderType === "Dine In" ? table || null : null,
      guests: guests || null,
      customer_name: orderType === "Takeaway" || orderType === "Delivery" ? custName || null : null,
      customer_phone: orderType === "Takeaway" || orderType === "Delivery" ? custPhone || null : null,
      delivery_address: orderType === "Delivery" ? custAddr || null : null,
      // a walk-in customer picked in the guest panel (a room bill is its guest's)
      guest: draftGuest && !(orderType === "Room Service" || (orderType === "Dine In" && room)) ? draftGuest.guest : null,
      items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
    }
  }
  const newBillLabel = () =>
    orderType === "Dine In" && table ? `Table ${table}`
      : orderType === "Room Service" && room ? `Room ${room.split("-").pop()}`
        : `${orderType}${custName ? ` · ${custName.split(" ")[0]}` : ""}`

  /** Create the bill (optionally firing the KOT). Returns the order id. */
  async function createBill(fire: boolean) {
    if (fire) {
      // one round trip: create, discount, confirm and fire on the server
      const kot = await call<{ order: string; kot_no: number | null; fired_items: { item_name: string; qty: number; instructions?: string | null }[]; ticket?: KotTicket }>(
        "kamra.pos.send_order", { ...newBillArgs(), discount: disc > 0 ? disc : 0 })
      maybePrintKot(kot, newBillLabel(), orderType,
        custName || null, orderType === "Delivery" ? custAddr || null : null)
      return kot.order
    }
    const r = await call<{ order: string }>("kamra.pos.create_order", newBillArgs())
    if (disc > 0) await call("kamra.pos.apply_discount", { order: r.order, amount: disc, reason: "" })
    await call("kamra.pos.confirm_order", { order: r.order })
    return r.order
  }

  async function kotAction() { // F6 - fire the kitchen ticket
    if (selected) {
      if (cart.length === 0) return
      await act(async () => {
        // one round trip: add the round and fire it on the server
        const kot = await call<{ kot_no: number | null; nc?: boolean; ticket?: KotTicket; fired_items: { item_name: string; qty: number; instructions?: string | null }[] }>(
          "kamra.pos.send_round", {
            order: selected,
            items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
          })
        if (detail) maybePrintKot(kot, orderLabel(detail), detail.order_type,
          detail.customer_name, detail.delivery_address, detail.nc_authorized_by)
        setCart([])
        // the till is free now; the bill panel catches up in the background
        void reloadDetail().catch(() => {})
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
  async function proceedToPay() { // F4 - opens the settle overlay
    setBillMenuOpen(false)
    setMoreOpen(false)
    if (selected && detail) {
      setSettling(true); setSheetNc(false)
      setMobilePane("bill")
    } else if (cart.length > 0) {
      await act(async () => {
        const order = await createBill(true)
        await openTab(order)
        setSettling(true)
      })
    }
  }
  async function settle(mode: string) {
    if (!selected) return
    const order = selected
    await act(async () => {
      await ensureUnlocked()
      await call("kamra.pos.pay_order", { order, mode })
      await sendBill(order)
      newOrder()
    })
  }
  /** Close at zero: Deliver posts NC bills / room-service to their homes. */
  async function settleDeliver() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.deliver_order", { order: selected })
      newOrder()
    })
  }
  /** A dine-in guest signs the bill to their room: link the stay, then
   *  Deliver posts it to their folio (billing rules and alcohol rule apply). */
  async function chargeToRoom() {
    if (!selected || !postRoom) return
    const order = selected
    await act(async () => {
      await call("kamra.pos.charge_to_room", { order, room: postRoom })
      await call("kamra.pos.deliver_order", { order })
      setPostRoom("")
      newOrder()
    })
  }
  /** The Complimentary tender: authorize the NC, then close the bill at zero. */
  async function settleNc() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.mark_nc", {
        order: selected, authorized_by: ncBy, note: ncNote, undo: 0,
      })
      await call("kamra.pos.deliver_order", { order: selected })
      newOrder()
    })
  }
  /** Bills and KOTs print on different stations. A bill printer set up for
   *  this till or outlet takes the bill; with none, this device prints it. */
  async function sendBill(order: string) {
    const routed = await call<{ unrouted: boolean }>("kamra.printing.print_bill", { order })
    if (!routed.unrouted) return
    const bill = await call<BillData>("kamra.pos.bill_data", { order })
    printThermal(`Bill ${order}`, billHtml(bill))
  }
  async function printBill() {
    if (!selected) return
    await sendBill(selected)
  }
  function reprintKot() {
    if (!detail) return
    const last = (detail.kot_tickets || []).at(-1)
    if (last?.items?.length) {
      printSavedKot(last, true)
      setPrintNote(translate("Reprinting KOT #{v0}.", { v0: String(last.kot_no) }))
      return
    }
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
  /** A supervisor approving food the kitchen has: re-confirm who they are
   *  with their own PIN pad (skipped where the property has no PINs). */
  async function selfApproval(kitchen: number) {
    if (kitchen > 0 && detail?.can_approve) await ensureUnlocked()
  }
  async function confirmVoid(a: VoidArgs) {
    if (!selected || !voiding) return
    const sent = voiding.kot_status !== "New" ? 1 : 0
    await act(async () => {
      await selfApproval(sent)
      await call("kamra.pos.void_item", { order: selected, item_row: voiding.row, ...a })
      setVoiding(null)
      await reloadDetail()
    })
  }
  /** A line nobody sent to the kitchen comes off: no reason, nothing cooked. */
  async function removeLine(row: string) {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.remove_item", { order: selected, item_row: row })
      await reloadDetail()
    })
  }
  async function confirmCancel(a: VoidArgs) {
    if (!selected) return
    await act(async () => {
      await selfApproval(detail?.kitchen_lines ?? 0)
      await call("kamra.pos.cancel_order", { order: selected, ...a })
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
    : cat === "All"
      ? allItems
      : (cats.find((c) => c.category === cat)?.items || [])

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
  const runningBills = open.filter((o) => !o.kot_fired)
  const kitchenBills = open.filter((o) => o.kot_fired && o.pending > 0)
  const billItemCount = (selected && detail ? detail.items.filter((i) => !i.voided).length : 0)
    + cart.reduce((s, l) => s + l.qty, 0)

  /* Tables / open bills / recent: drawer on tablet+desktop, own pane on phones.
     Menu + bill own the main row so items stay visible (POSNext-style). */
  const tablesPane = (
    <>
            <div className="shrink-0 rounded-xl border border-zinc-200 bg-white p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-500">{t("Running tables")}</h3>
                {tables.length > 0 && (
                  <button onClick={() => setReserveOpen((v) => !v)}
                    className="rounded-lg border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-600 hover:border-violet-400 hover:text-violet-700">
                    + {t("Reserve")}
                  </button>
                )}
              </div>
              {reserveOpen && (
                <div className="mb-2 space-y-1.5 rounded-xl border border-violet-200 bg-violet-50 p-2">
                  <div className="grid grid-cols-2 gap-1.5">
                    <select className={inputCls + " !py-1 text-xs"} value={resForm.table}
                      onChange={(e) => setResForm({ ...resForm, table: e.target.value })}>
                      <option value="">{translate("Table…")}</option>
                      {tables.filter((t) => !t.temp).map((t) => <option key={t.table} value={t.table}>{t.table}</option>)}
                    </select>
                    <input className={inputCls + " !py-1 text-xs"} type="datetime-local" value={resForm.at}
                      onChange={(e) => setResForm({ ...resForm, at: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <input className={inputCls + " !py-1 text-xs"} placeholder={t("Guest name")} value={resForm.guest}
                      onChange={(e) => setResForm({ ...resForm, guest: e.target.value })} />
                    <input className={inputCls + " !py-1 text-xs"} placeholder={t("Phone")} value={resForm.phone}
                      onChange={(e) => setResForm({ ...resForm, phone: e.target.value })} />
                  </div>
                  <div className="flex gap-1.5">
                    <input className={inputCls + " !w-20 !py-1 text-xs"} placeholder={t("Party")} inputMode="numeric" value={resForm.party}
                      onChange={(e) => setResForm({ ...resForm, party: e.target.value.replace(/\D/g, "") })} />
                    <Button className="flex-1 !py-1 text-xs" disabled={busy || !resForm.table || !resForm.guest.trim() || !resForm.at}
                      onClick={saveReservation}>{t("Reserve")}</Button>
                    <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setReserveOpen(false)}>✕</Button>
                  </div>
                </div>
              )}
              {tables.length > 0 ? (
                <>
                  <div className="relative mb-2">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
                    <input className={inputCls + " !py-1 pl-8 text-xs"} placeholder={t("Search table…")}
                      value={tableQuery} onChange={(e) => setTableQuery(e.target.value)} />
                  </div>
                  <div className="mb-1 flex flex-wrap gap-1">
                    {([["all", t("All ({n})", { n: tables.length })], ["available", t("Available ({n})", { n: availableCount })],
                       ["occupied", t("Occupied ({n})", { n: tables.length - availableCount })]] as const).map(([k, l]) => (
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
                          {a === "All" ? t("All") : a}
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
                        {group.map((tile) => (
                          <button key={tile.table}
                            onClick={() => tile.state === "reserved" ? setResTile(resTile === tile.table ? null : tile.table)
                              : tile.state === "cleaning" ? cleanTable(tile)
                                : tile.bills === 0 ? newOrder(tile.table)
                                  : tile.bills === 1 ? openTab(tile.orders[0].order)
                                    : setChooser(chooser === tile.table ? null : tile.table)}
                            className={"relative rounded-xl border p-2 text-left transition " + TILE[tile.state] +
                              (tile.temp ? " border-dashed" : "") +
                              (tile.orders.some((b) => b.order === selected) || chooser === tile.table ? " ring-2 ring-brand-600 ring-offset-1" :
                                tile.bills === 0 && selected === null && table === tile.table ? " ring-2 ring-brand-600 ring-offset-1" : "")}>
                            {tile.bills > 1 && (
                              <span className="absolute -right-1.5 -top-1.5 flex items-center gap-0.5 rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                                <Users className="size-2.5" />{tile.bills}
                              </span>
                            )}
                            <div className="flex items-baseline justify-between gap-1">
                              <span className="truncate text-sm font-bold">{tile.table}</span>
                              {tile.bills > 0 && tile.since && (
                                <span className="shrink-0 text-[9px] font-medium opacity-60">{ago(tile.since)}</span>
                              )}
                            </div>
                            <div className="truncate text-[10px] opacity-70">
                              {tile.bills > 0
                                ? <>{cur()}{inr(tile.order_total)}{tile.guests ? <> · <Users className="inline size-2.5" />{tile.guests}</> : null}</>
                                : tile.state === "reserved" ? `${t("Res")} ${tile.res_time} · ${tile.res_guest || ""}`
                                  : tile.state === "cleaning" ? t("Cleaning")
                                    : tile.seats ? t("{n} seats", { n: tile.seats }) : " "}
                            </div>
                          </button>
                        ))}
                        {groupName === null && visibleTables.length === 0 && (
                          <p className="col-span-3 py-3 text-center text-xs text-zinc-400">{t("No tables match.")}</p>
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
                            {t.res_party ? translate(" · {v0} pax", { v0: String(t.res_party) }) : ""}
                          </span>
                          <button onClick={() => setResTile(null)} className="text-violet-400 hover:text-violet-700">✕</button>
                        </div>
                        {t.res_phone && <p className="text-[11px] text-violet-700">{t.res_phone}</p>}
                        <div className="flex gap-1.5">
                          <Button className="flex-1 !py-1 text-xs" disabled={busy} onClick={() => seatReservation(t)}>{translate("Seat now")}</Button>
                          <Button variant="outline" className="!px-2 !py-1 text-xs" disabled={busy} onClick={() => closeReservation(t, "No Show")}>{translate("No show")}</Button>
                          <Button variant="outline" className="!px-2 !py-1 text-xs text-rose-600" disabled={busy} onClick={() => closeReservation(t, "Cancelled")}>{translate("Cancel")}</Button>
                        </div>
                      </div>
                    )
                  })()}
                  {/* what the tile colours mean */}
                  <div className="mb-2 flex flex-wrap gap-x-2.5 gap-y-1 text-[10px] text-zinc-500">
                    {([["Vacant", "border border-zinc-300 bg-white"],
                       ["Running", "border border-amber-300 bg-amber-50"],
                       ["In kitchen", "border border-sky-300 bg-sky-50"],
                       ["Ready", "border border-emerald-300 bg-emerald-50"],
                       ["Reserved", "border border-violet-300 bg-violet-50"],
                       ["Cleaning", "border border-zinc-300 bg-zinc-100"]] as const).map(([l, c]) => (
                      <span key={l} className="flex items-center gap-1">
                        <span className={"size-2.5 rounded " + c} />{l}
                      </span>
                    ))}
                  </div>
                  <button onClick={() => { newOrder(); setOrderType("Dine In"); setCustomTable(true) }}
                    className="w-full rounded-xl border border-dashed border-zinc-300 px-2 py-1.5 text-xs font-medium text-zinc-500 transition hover:border-brand-500 hover:text-brand-700">
                    <Plus className="mr-0.5 inline size-3.5" />{translate("Temp table")}</button>
                  {chooser && (() => {
                    const t = tables.find((x) => x.table === chooser)
                    if (!t) return null
                    return (
                      <div className="mt-2 space-y-1 rounded-xl bg-zinc-50 p-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-zinc-500">{t.table} - {t.bills}{translate(" bills")}</span>
                          <button onClick={() => setChooser(null)} className="text-zinc-400 hover:text-zinc-600">✕</button>
                        </div>
                        {t.orders.map((b) => (
                          <button key={b.order} onClick={() => openTab(b.order)}
                            className={"flex w-full items-center justify-between rounded-lg border px-2 py-1 text-xs transition " + TILE[b.state]}>
                            <span>{translate(b.label)}</span><span className="tabular-nums">{cur()}{inr(b.order_total)}</span>
                          </button>
                        ))}
                        <button onClick={() => newOrder(t.table)}
                          className="w-full rounded-lg border border-dashed border-zinc-400 px-2 py-1 text-xs text-zinc-600 hover:border-brand-500 hover:text-brand-700">
                          <Plus className="mr-0.5 inline size-3" />{translate("New bill")}</button>
                      </div>
                    )
                  })()}
                </>
              ) : (
                <p className="py-2 text-xs text-zinc-400">{translate("No table layout for this outlet yet - add tables (one per line,")}<code className="mx-1 rounded bg-zinc-100 px-1">T1:4</code>{translate(" = 4 seats) on the POS Outlet.")}</p>
              )}
              {looseBills.length > 0 && (
                <div className="mt-3 border-t border-zinc-100 pt-2">
                  <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{translate("Rooms · takeaway · delivery")}</h4>
                  <div className="flex flex-wrap gap-1">
                    {looseBills.map((o) => (
                      <button key={o.name} onClick={() => openTab(o.name)}
                        className={"rounded-lg border px-2 py-1 text-xs transition " +
                          (selected === o.name ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-zinc-200 bg-white hover:border-brand-400")}>
                        {translate(o.label)} <span className="tabular-nums text-zinc-400">{cur()}{inr(o.order_total)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {(runningBills.length > 0 || kitchenBills.length > 0) && (
              <div className="shrink-0 rounded-xl border border-zinc-200 bg-white p-3">
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-zinc-500">{t("Open bills")}</h3>
                {runningBills.length > 0 && (
                  <div className="mb-2">
                    <p className="mb-1 text-[10px] font-semibold uppercase text-amber-700">{t("Open, not sent to kitchen")}</p>
                    <ul className="space-y-1">
                      {runningBills.map((o) => (
                        <li key={o.name}>
                          <button onClick={() => openTab(o.name)}
                            className={cn("flex w-full items-center justify-between gap-2 rounded-lg border px-2 py-1.5 text-xs",
                              o.stale ? "border-rose-300 bg-rose-50" : "border-amber-200 bg-amber-50",
                              selected === o.name && "ring-2 ring-brand-600")}>
                            <span className={cn("min-w-0 truncate font-semibold", o.stale ? "text-rose-900" : "text-amber-900")}>{translate(o.label)}</span>
                            <span className="flex shrink-0 items-center gap-1.5">
                              <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
                                o.stale ? "bg-rose-600 text-white" : "bg-amber-200 text-amber-900")}
                                title={t("Not sent to the kitchen for {mins} min", { mins: o.age_min ?? 0 })}>
                                {ago(o.creation)}
                              </span>
                              <span className="tabular-nums text-amber-800">{cur()}{inr(o.order_total)}</span>
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                    {runningBills.some((o) => o.stale) && (
                      <p className="mt-1 text-[11px] text-rose-700">{t("Red bills were never sent. Send them, or cancel with a reason.")}</p>
                    )}
                  </div>
                )}
                {kitchenBills.length > 0 && (
                  <div>
                    <p className="mb-1 text-[10px] font-semibold uppercase text-sky-700">{t("In kitchen / not settled")}</p>
                    <ul className="space-y-1">
                      {kitchenBills.map((o) => (
                        <li key={o.name}>
                          <button onClick={() => openTab(o.name)}
                            className={"flex w-full items-center justify-between rounded-lg border border-sky-200 bg-sky-50 px-2 py-1.5 text-xs " +
                              (selected === o.name ? "ring-2 ring-brand-600" : "")}>
                            <span className="font-semibold text-sky-900">
                              {translate(o.label)}{o.kot_no ? translate(" · KOT {v0}", { v0: String(o.kot_no) }) : ""}
                            </span>
                            <span className="tabular-nums text-sky-800">{cur()}{inr(o.order_total)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <div className="shrink-0 rounded-xl border border-zinc-200 bg-white p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-500">{t("Recent")}</h3>
                <button onClick={() => { setTablesOpen(false); setPanel("orders") }}
                  className="text-[11px] font-semibold text-brand-700 hover:underline">
                  {t("All orders")}
                </button>
              </div>
              <ul className="space-y-1">
                {recent.map((r) => (
                  <li key={r.name}>
                    <button onClick={() => r.open ? openTab(r.name) : (setTablesOpen(false), setPanel("orders"))}
                      className={"flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs " +
                        (r.open ? "hover:bg-brand-50" : "opacity-60 hover:bg-zinc-50")}>
                      <span className="min-w-0">
                        <span className="font-medium text-zinc-700">{translate(r.label)}</span>
                        <span className="ml-1 text-zinc-400">· {translate(r.order_type)}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5 tabular-nums">
                        <span className="font-semibold">{cur()}{inr(r.order_total)}</span>
                        {r.nc ? <span className="rounded bg-amber-50 px-1 text-[10px] font-bold text-amber-700">{translate("NC")}</span>
                          : r.paid ? <span className="rounded bg-emerald-50 px-1 text-[10px] font-medium text-emerald-700">{translate(r.payment_mode)}</span>
                            : r.status === "Cancelled" ? <span className="rounded bg-rose-50 px-1 text-[10px] font-medium text-rose-600">✕</span>
                              : null}
                        <span className="text-zinc-400">{ago(r.modified)}</span>
                      </span>
                    </button>
                  </li>
                ))}
                {recent.length === 0 && <p className="py-2 text-center text-xs text-zinc-400">{t("No orders yet today.")}</p>}
              </ul>
            </div>
    </>
  )

  return (
    <div ref={rootRef} className={cn("flex h-full min-h-0 flex-col gap-3", floorOn && "bg-zinc-50 p-3")}>
      {/* header - outlet, order type, New Bill; secondary tools in overflow */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-xl font-bold text-zinc-800">
          <UtensilsCrossed className="size-5 text-brand-600" />
          <span className="hidden sm:inline">{t("Restaurant POS")}</span>
          <select className={inputCls + " !w-auto font-normal"} value={outlet} onChange={(e) => {
            setOutlet(e.target.value); newOrder()
            try { localStorage.setItem(OUTLET_KEY, e.target.value) } catch { /* private mode */ }
          }}>
            {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
          </select>
        </h1>
        <div className="flex rounded-xl border border-zinc-200 bg-white p-1 shadow-sm">
          {ORDER_TYPES.map((ot) => (
            <button key={ot} onClick={() => { setOrderType(ot); if (selected) newOrder(); }}
              className={"rounded-lg px-3 py-1.5 text-sm transition " +
                ((selected && detail ? detail.order_type : orderType) === ot
                  ? "bg-brand-600 font-semibold text-white"
                  : "text-zinc-600 hover:bg-zinc-50")}>
              {t(ot)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setTablesOpen(true)}
            className="hidden items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50 md:inline-flex">
            <LayoutGrid className="size-4" />{t("Tables")}
            {tables.filter((x) => x.state !== "vacant" && x.state !== "cleaning").length > 0 && (
              <span className="rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {tables.filter((x) => x.state !== "vacant" && x.state !== "cleaning").length}
              </span>
            )}
          </button>
          {floorOn && (
            <button type="button" onClick={exitFloor}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs font-semibold text-zinc-600 hover:bg-zinc-50"
              title={t("Show the app menu (Esc)")}>
              <Menu className="size-4" />{t("Menu")}
            </button>
          )}
          {/* old and open bills are always one labelled tap away, never only under the menu */}
          <button type="button" onClick={() => setPanel("orders")}
            className="relative inline-flex items-center gap-1.5 rounded-lg border border-brand-600 bg-white px-3 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-50"
            title={t("Today's orders, and the bills still open")}>
            <ListOrdered className="size-4" />
            {t("Orders")}
            {open.some((o) => o.stale) && <span className="size-2 rounded-full bg-rose-600" aria-label={t("A bill was never sent")} />}
          </button>
          <button type="button" onClick={() => setHistoryOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-400 bg-white px-3 py-2 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
            title={t("Every past bill: search, filter by date, type and payment, and export")}>
            <History className="size-4" />
            {t("Order history")}
          </button>
          <Button onClick={() => newOrder()}>
            <Plus className="size-4" />{t("New Bill")}
            <kbd className="rounded bg-white/20 px-1 text-[10px]">F2</kbd>
          </Button>
          <div className="relative">
            <button type="button" onClick={() => setMoreOpen((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-400 bg-white px-2.5 py-2 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
              title={t("More")} aria-label={t("More")} aria-expanded={moreOpen}>
              <MoreVertical className="size-4" />
              <span className="hidden lg:inline">{t("More")}</span>
              {open.some((o) => o.stale) && (
                <span className="absolute right-1 top-1 size-2 rounded-full bg-rose-600" aria-label={t("A bill was never sent")} />
              )}
            </button>
            {moreOpen && (
              <>
                <div className="fixed inset-0 z-20" onClick={() => setMoreOpen(false)} aria-hidden />
                <div className="absolute right-0 top-full z-30 mt-1 w-72 max-h-[min(70vh,28rem)] overflow-y-auto rounded-xl border border-zinc-200 bg-white py-1 shadow-lg">
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                    {t("Open bills")}{open.length > 0 ? ` · ${open.length}` : ""}
                  </div>
                  {open.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-zinc-400">{t("No open bills")}</p>
                  ) : (
                    open.map((o) => {
                      const hint = !o.kot_fired
                        ? (o.stale ? t("Not sent") : t("Draft"))
                        : o.pending > 0 ? t("In kitchen") : t("Ready / unpaid")
                      return (
                        <button key={o.name} type="button"
                          onClick={() => { setMoreOpen(false); void openTab(o.name) }}
                          className={cn(
                            "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50",
                            selected === o.name && "bg-brand-50",
                            !!o.stale && "text-rose-800",
                          )}>
                          <span className="min-w-0 flex-1 truncate font-medium">{translate(o.label)}</span>
                          <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{translate(hint)}</span>
                          <span className="shrink-0 tabular-nums text-xs font-semibold text-zinc-700">{cur()}{inr(o.order_total)}</span>
                        </button>
                      )
                    })
                  )}
                  <button type="button" onClick={() => { setPanel("orders"); setMoreOpen(false) }}
                    className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm font-medium text-brand-700 hover:bg-brand-50">
                    <ListOrdered className="size-4" />
                    {t("See all orders / history")}
                  </button>
                  <button type="button" onClick={() => { setHistoryOpen(true); setMoreOpen(false) }}
                    title={t("Every past bill: search, filter by date, type and payment, and export")}
                    className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm font-medium text-brand-700 hover:bg-brand-50">
                    <History className="size-4" />
                    {t("Order history")}
                  </button>

                  <div className="my-1 border-t border-zinc-100" />
                  {autoKot ? (
                    <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-brand-800">
                      <Printer className="size-4" />
                      {t("KOT prints on send")}
                    </div>
                  ) : (
                    <button type="button" onClick={() => setPrintKot((v) => !v)}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50">
                      <Printer className="size-4 text-zinc-500" />
                      {printKot ? t("KOT printer on") : t("KOT printer off")}
                    </button>
                  )}

                  <div className="my-1 border-t border-zinc-100" />
                  <button type="button" onClick={() => { toggleFocus(); setMoreOpen(false) }}
                    className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50">
                    <Focus className="size-4 text-zinc-500" />
                    {kioskOn ? t("Show PMS menus") : t("Focus mode - hide PMS menus")}
                  </button>
                  <button type="button" onClick={() => { toggleBrowserFs(); setMoreOpen(false) }}
                    className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50">
                    {browserFs ? <Minimize2 className="size-4 text-zinc-500" /> : <Maximize2 className="size-4 text-zinc-500" />}
                    {browserFs ? t("Exit full screen") : t("Full screen till")}
                  </button>
                  <button type="button" onClick={() => { setMoreOpen(false); exitFloor(); navigate("/dashboard") }}
                    className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50">
                    <LogOut className="size-4 text-zinc-500" />
                    {t("Leave POS")}
                  </button>
                  <p className="border-t border-zinc-100 px-3 py-2 text-[10px] leading-snug text-zinc-400">
                    <Keyboard className="me-1 inline size-3 align-text-bottom" />{translate("F2 New · F3 Bills · F4 Settle · Esc menus")}</p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* phone: pane switcher */}
      <div className="flex shrink-0 rounded-xl border border-zinc-200 bg-white p-1 shadow-sm md:hidden">
        {([["tables", t("Tables")], ["menu", t("Menu")], ["bill", t("Bill")]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setMobilePane(k)}
            className={cn("flex-1 rounded-lg px-3 py-2 text-sm font-medium transition",
              mobilePane === k ? "bg-brand-600 text-white" : "text-zinc-600")}>
            {l}{k === "bill" && billItemCount > 0 ? ` · ${Math.round(billItemCount)}` : ""}
          </button>
        ))}
      </div>

      {error && <div className="shrink-0 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(error)}</div>}
      {printTip && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span>
            {t("Printing waited on the print dialog. Start Chrome with --kiosk-printing on this till to print KOTs instantly.")}{" "}
            <a className="font-semibold underline" href="https://kamrapms.com/docs/features#fast-silent-printing"
              target="_blank" rel="noreferrer">{t("How")}</a>
          </span>
          <button className="text-xs font-semibold" onClick={() => setPrintTip(false)}>{t("Dismiss")}</button>
        </div>
      )}
      {printNote && (
        <div className="flex shrink-0 items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          <span>{printNote}</span>
          <button className="text-xs font-semibold" onClick={() => setPrintNote(null)}>{t("Dismiss")}</button>
        </div>
      )}
      {open.length > 0 && (
        <div className="shrink-0">
          <RunningStrip
            open={open}
            selected={selected}
            onOpen={(name) => void openTab(name, { popup: true })}
            onSeeAll={() => setBillsPopupOpen(true)}
          />
        </div>
      )}

      <div className="flex min-h-0 flex-1 items-stretch gap-3">
        {/* tables: phone pane only - desktop uses the header drawer */}
        <div className={cn("min-h-0 w-full flex-col gap-2 overflow-y-auto md:hidden",
          mobilePane === "tables" ? "flex" : "hidden")}>
          {tablesPane}
        </div>

        {/* ── menu: category rail + item grid (the long add-items surface) ── */}
        <div className={cn(
          "flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm",
          mobilePane === "menu" ? "flex" : "hidden md:flex",
        )}>
          {/* long side categories */}
          <nav className="hidden w-[9.5rem] shrink-0 flex-col overflow-y-auto border-e border-zinc-100 bg-zinc-50/80 sm:flex lg:w-44" aria-label={t("Categories")}>
            <p className="sticky top-0 z-10 border-b border-zinc-100 bg-zinc-50/95 px-3 py-2.5 text-[10px] font-bold uppercase tracking-wide text-zinc-400">
              {t("Menu")}
            </p>
            {(["All", ...cats.map((c) => c.category)] as string[]).map((c) => {
              const active = cat === c && !query.trim()
              const count = c === "All" ? allItems.length : (cats.find((x) => x.category === c)?.items.length ?? 0)
              return (
                <button key={c} type="button" onClick={() => { setCat(c); setQuery("") }}
                  className={cn(
                    "flex items-center justify-between gap-2 border-b border-zinc-100/80 px-3 py-3 text-left text-sm transition",
                    active
                      ? "bg-brand-600 font-semibold text-white"
                      : "font-medium text-zinc-700 hover:bg-white hover:text-brand-800",
                  )}>
                  <span className="min-w-0 truncate">{c === "All" ? t("All") : c}</span>
                  <span className={cn("shrink-0 tabular-nums text-[11px]", active ? "text-white/80" : "text-zinc-400")}>
                    {count}
                  </span>
                </button>
              )
            })}
          </nav>

          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="shrink-0 space-y-2 border-b border-zinc-100 p-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
                <input className={inputCls + " h-11 pl-9 text-base"} placeholder={t("Search menu items…")}
                  value={query} onChange={(e) => setQuery(e.target.value)} />
              </div>
              {/* phone: horizontal chips when the side rail is hidden */}
              <div className="flex gap-1.5 overflow-x-auto pb-0.5 sm:hidden">
                {["All", ...cats.map((c) => c.category)].map((c) => (
                  <button key={c} type="button" onClick={() => { setCat(c); setQuery("") }}
                    className={cn("shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition",
                      cat === c && !query.trim()
                        ? "bg-brand-600 text-white"
                        : "bg-zinc-100 text-zinc-600")}>
                    {c === "All" ? t("All") : c}
                  </button>
                ))}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3 xl:grid-cols-4 2xl:grid-cols-5">
                {shownItems.map((it) => <MenuCard key={it.name} it={it} onAdd={() => addToCart(it)} />)}
                {shownItems.length === 0 && (
                  <p className="col-span-full py-16 text-center text-sm text-zinc-400">{t("No matches.")}</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── right cart: header | tall item scroll | pay footer (Restro-style) ── */}
        <div className={cn(
          "grid h-full min-h-0 w-full grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm",
          "md:w-[min(42vw,36rem)] md:shrink-0 md:basis-[min(42vw,36rem)]",
          mobilePane === "bill" ? "grid" : "hidden md:grid",
        )}>
          {/* row 1 - thin who/where chrome */}
          <div className="space-y-1.5 border-b border-zinc-100 px-3 py-2">
            {selected && detail ? (
              <div className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <h2 className="truncate text-sm font-bold text-zinc-900">{translate(orderLabel(detail))}</h2>
                    <span className="shrink-0 truncate text-[11px] text-zinc-500">
                      {detail.kot_no ? translate("KOT #{v0} · ", { v0: String(detail.kot_no) }) : ""}{translate(detail.status)}
                      {detail.guests ? ` · ${detail.guests}` : ""}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {detail.table_no && detail.status !== "Delivered" && (
                    <button type="button" title={t("New bill on this table")}
                      onClick={() => newOrder(detail.table_no!)}
                      className="rounded-md border border-dashed border-zinc-300 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 hover:border-brand-500 hover:text-brand-700">
                      + {t("bill")}
                    </button>
                  )}
                  <button type="button" onClick={() => setBillsPopupOpen(true)}
                    className="rounded-md border border-zinc-200 p-1 text-zinc-500 hover:border-brand-400 hover:bg-brand-50"
                    title={t("Open full bill")} aria-label={t("Open full bill")}>
                    <Maximize2 className="size-3.5" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                {orderType === "Dine In" && (
                  <>
                    <div className="grid grid-cols-2 gap-1.5">
                      {tables.length > 0 && !customTable ? (
                        <select className={inputCls + " !py-1.5 text-sm"} value={chooser || table}
                          onChange={(e) => pickCartTable(e.target.value)}>
                          <option value="">{t("Table…")}</option>
                          {tables.map((t) => (
                            <option key={t.table} value={t.table}>
                              {t.table}{t.seats ? ` (${t.seats})` : ""}{t.bills > 0 ? ` · ${t.bills}` : ""}
                            </option>
                          ))}
                          <option value="__custom__">{t("Temp / custom table…")}</option>
                        </select>
                      ) : (
                        <div className="flex gap-1">
                          <input autoFocus={customTable} className={inputCls + " !py-1.5"} placeholder={t("Table name")}
                            value={table} onChange={(e) => setTable(e.target.value)} />
                          {customTable && (
                            <Button variant="ghost" className="!px-2" onClick={() => { setCustomTable(false); setTable(""); setChooser(null) }}>✕</Button>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-1 rounded-lg border border-zinc-300 px-2">
                        <Users className="size-3.5 text-zinc-400" />
                        <input className="w-full bg-transparent py-1.5 text-sm focus:outline-none" placeholder={t("Guests")}
                          inputMode="numeric" value={guests} onChange={(e) => setGuests(e.target.value.replace(/\D/g, ""))} />
                      </div>
                    </div>
                    {tables.some((x) => x.bills > 0) && (
                      <p className="text-[10px] leading-snug text-zinc-400">
                        {t("Pick a table with an open bill to add items to it.")}
                      </p>
                    )}
                    {chooser && (() => {
                      const tile = tables.find((x) => x.table === chooser)
                      if (!tile || tile.bills < 2) return null
                      return (
                        <div className="space-y-1 rounded-lg border border-brand-200 bg-brand-50/50 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-[11px] font-semibold text-brand-800">
                              {t("Table {n} has {count} bills", { n: tile.table, count: tile.bills })}
                            </p>
                            <button type="button" className="text-zinc-400 hover:text-zinc-600"
                              onClick={() => setChooser(null)} aria-label={t("Close")}>✕</button>
                          </div>
                          {tile.orders.map((b) => (
                            <button key={b.order} type="button" onClick={() => { setChooser(null); void openTab(b.order) }}
                              className={"flex w-full items-center justify-between rounded-md border px-2 py-1.5 text-xs transition " + TILE[b.state]}>
                              <span className="font-medium">{translate(b.label)}</span>
                              <span className="tabular-nums">{cur()}{inr(b.order_total)}</span>
                            </button>
                          ))}
                          <button type="button" onClick={() => { setChooser(null); newOrder(tile.table) }}
                            className="w-full rounded-md border border-dashed border-zinc-400 px-2 py-1.5 text-xs text-zinc-600 hover:border-brand-500 hover:text-brand-700">
                            <Plus className="me-0.5 inline size-3" />{t("New bill on this table")}
                          </button>
                        </div>
                      )
                    })()}
                  </>
                )}
                {orderType === "Room Service" && (
                  <RoomPicker rooms={rooms} value={room} onChange={setRoom} onOpen={loadRooms}
                    placeholder={(rooms.length ? t("Room…") : t("No guests in house"))} />
                )}
                {orderType === "Dine In" && rooms.length > 0 && (
                  <RoomPicker rooms={rooms} value={room} onChange={setRoom} onOpen={loadRooms}
                    placeholder={t("Charge to room (optional)…")} />
                )}
                {isNewCustomerType && (
                  <>
                    <div className="grid grid-cols-2 gap-1.5">
                      <input className={inputCls + " !py-1.5"} placeholder={t("Customer name")} value={custName} onChange={(e) => setCustName(e.target.value)} />
                      <input className={inputCls + " !py-1.5"} placeholder={t("Phone")} value={custPhone} onChange={(e) => setCustPhone(e.target.value)} />
                    </div>
                    {orderType === "Delivery" && (
                      <input className={inputCls + " !py-1.5"} placeholder={t("Delivery address")} value={custAddr} onChange={(e) => setCustAddr(e.target.value)} />
                    )}
                  </>
                )}
              </div>
            )}
            {(() => {
              const roomId = selected && detail ? detail.room : (orderType === "Room Service" || orderType === "Dine In") ? room || null : null
              const stay = roomId ? rooms.find((r) => r.room === roomId) : undefined
              const name = selected && detail
                ? (detail.room ? stay?.guest_name ?? null : detail.guest ? detail.customer_name : null)
                : roomId ? stay?.guest_name ?? null : draftGuest?.full_name ?? null
              const blocked = stay && Number(stay.room_charges_allowed ?? 1) === 0
              return (
                <button type="button" onClick={() => setPanel("guest")}
                  className={cn("flex w-full items-center gap-1.5 rounded-md border px-2 py-1 text-start text-[11px] transition",
                    name ? "border-zinc-200 bg-zinc-50 hover:border-brand-400" : "border-dashed border-zinc-300 text-zinc-500 hover:border-brand-500 hover:text-brand-700")}>
                  {roomId ? <BedDouble className="size-3 shrink-0 text-violet-600" /> : <UserRound className="size-3 shrink-0" />}
                  <span className="min-w-0 flex-1 truncate">
                    {name
                      ? <><span className="font-semibold text-zinc-800">{name}</span>{stay ? <span className="text-zinc-500"> · {t("Room {n}", { n: stay.room_number })}</span> : null}</>
                      : roomId ? t("In-house guest") : t("Add customer (phone or name)")}
                  </span>
                  {blocked && <span className="shrink-0 rounded-full bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">{t("No room charges")}</span>}
                </button>
              )
            })()}
          </div>

          {/* row 2 - THIS is the cart: tall scroll, large readable lines */}
          <div className="flex min-h-0 flex-col overflow-hidden bg-zinc-50/60">
            <div className="flex shrink-0 items-center justify-between gap-2 border-b border-zinc-200/80 bg-white px-3 py-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wide text-zinc-600">
                {t("Items")} · {cart.reduce((s, l) => s + l.qty, 0) + (detail?.items.filter((i) => !i.voided).length ?? 0)}
              </span>
              {cart.length > 0 && (
                <button type="button" onClick={() => setCart([])}
                  className="text-[11px] font-semibold text-zinc-500 hover:text-rose-600">
                  {t("Clear new")}
                </button>
              )}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2.5 py-2">
              {cart.length === 0 && !(selected && detail?.items.length) ? (
                <div className="flex h-full min-h-[18rem] flex-col items-center justify-center gap-2 px-4 text-center">
                  <UtensilsCrossed className="size-12 text-zinc-300" />
                  <p className="text-base font-semibold text-zinc-600">{t("No items yet")}</p>
                  <p className="max-w-[14rem] text-xs text-zinc-400">{t("Select items from the menu")}</p>
                </div>
              ) : (
                <ul className="space-y-2 pb-3">
                  {cart.map((l) => (
                    <li key={l.menu_item}
                      className="rounded-xl border border-zinc-200 bg-white p-3 shadow-sm">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="text-base font-bold leading-snug text-zinc-900">{l.item_name}</div>
                          <div className="mt-1 text-sm font-semibold tabular-nums text-brand-700">
                            {cur()}{inr(l.price)} × {l.qty} = {cur()}{inr(l.qty * l.price)}
                          </div>
                        </div>
                        <button type="button" onClick={() => setQty(l.menu_item, -l.qty)} aria-label={t("Remove")}
                          className="grid size-9 shrink-0 place-items-center rounded-lg text-rose-500 hover:bg-rose-50">
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                      <div className="mt-2.5 flex items-center gap-2">
                        <button type="button" onClick={() => setQty(l.menu_item, -1)} aria-label={translate("One less")}
                          className="grid size-11 place-items-center rounded-lg border-2 border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50">
                          <Minus className="size-4" />
                        </button>
                        <span className="min-w-[2.25rem] text-center text-xl font-bold tabular-nums text-zinc-900">{l.qty}</span>
                        <button type="button" onClick={() => setQty(l.menu_item, 1)} aria-label={translate("One more")}
                          className="grid size-11 place-items-center rounded-lg bg-brand-600 text-white hover:bg-brand-700">
                          <Plus className="size-4" />
                        </button>
                        <input className="ms-auto min-w-0 flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-2.5 text-xs text-zinc-800 placeholder:text-zinc-400"
                          placeholder={t("Notes")}
                          value={l.instructions} onChange={(e) => setInstr(l.menu_item, e.target.value)} />
                      </div>
                    </li>
                  ))}

                  {selected && detail && detail.items.length > 0 && (
                    <>
                      {cart.length > 0 && (
                        <li className="list-none pt-1 text-[10px] font-bold uppercase tracking-wide text-zinc-400">
                          {t("Already on bill")}
                        </li>
                      )}
                      {!!detail.nc && (
                        <li className="list-none rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
                          <span className="font-bold">{t("COMPLIMENTARY")}</span>
                          <span className="ms-1">{t("auth")}: {detail.nc_authorized_by}{detail.nc_note ? ` · ${detail.nc_note}` : ""}</span>
                        </li>
                      )}
                      {splitMode && (
                        <li className="list-none rounded-lg bg-brand-50 px-2.5 py-1.5 text-xs text-brand-700">
                          {t("Tick the lines moving to the new bill.")}
                        </li>
                      )}
                      {detail.items.map((it) => (
                        <li key={it.row}
                          className={cn(
                            "flex items-center justify-between gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-3",
                            !!it.voided && "opacity-45",
                          )}>
                          <div className="flex min-w-0 items-start gap-2">
                            {splitMode && !it.voided && (
                              <input type="checkbox" className="mt-1 accent-brand-600"
                                checked={splitSel.has(it.row)} onChange={() => toggleSplitSel(it.row)} />
                            )}
                            <div className="min-w-0">
                              <div className={cn("text-[15px] font-bold text-zinc-900", !!it.voided && "line-through")}>
                                {Math.round(it.qty)}× {it.item_name}
                              </div>
                              {!it.voided && (
                                <div className="mt-0.5 text-xs text-zinc-500">
                                  {it.kot_status === "New" ? t("not sent")
                                    : it.kot_status === "Prepared" ? t("Prepared") : t("In kitchen")}
                                  {it.instructions ? ` · ${it.instructions}` : ""}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
                            <span className="text-base font-bold tabular-nums text-zinc-900">{cur()}{inr(it.amount)}</span>
                            {!splitMode && !it.voided && detail.status !== "Delivered" && detail.status !== "Cancelled" && (
                              it.kot_status === "New" ? (
                                <button type="button" title={t("Remove (not sent to the kitchen)")}
                                  disabled={busy} onClick={() => removeLine(it.row)}
                                  className="grid size-10 place-items-center rounded-lg text-zinc-400 hover:bg-rose-50 hover:text-rose-500">
                                  <Trash2 className="size-4" />
                                </button>
                              ) : (
                                <button type="button" title={t("Void (the kitchen has it)")}
                                  onClick={() => { setVoiding(it); setCancelling(false) }}
                                  className="grid size-10 place-items-center rounded-lg text-zinc-300 hover:bg-rose-50 hover:text-rose-500">
                                  <XCircle className="size-4" />
                                </button>
                              )
                            )}
                          </div>
                        </li>
                      ))}
                      {voiding && (
                        <li className="list-none">
                          <VoidApproval outlet={outlet} busy={busy}
                            title={t("Void {item}", { item: voiding.item_name })}
                            kitchenCount={voiding.kot_status !== "New" ? 1 : 0}
                            canApprove={!!detail.can_approve}
                            confirmLabel={t("Void item")}
                            onConfirm={confirmVoid} onClose={() => setVoiding(null)} />
                        </li>
                      )}
                      {splitMode && (
                        <li className="flex list-none gap-1.5">
                          <Button className="flex-1" disabled={busy || splitSel.size === 0 ||
                            splitSel.size >= detail.items.filter((i) => !i.voided).length}
                            onClick={confirmSplit}>
                            <Scissors className="size-4" />{t("Move {n} to new bill", { n: splitSel.size || "" })}
                          </Button>
                          <Button variant="ghost" onClick={() => { setSplitMode(false); setSplitSel(new Set()) }}>✕</Button>
                        </li>
                      )}
                    </>
                  )}
                </ul>
              )}
            </div>
          </div>

          {/* row 3 - compact totals + actions only */}
          <div className="border-t border-zinc-200 bg-white px-3 py-2">
            <div className="mb-2 flex items-end justify-between gap-2">
              <div className="min-w-0 text-[11px] leading-snug text-zinc-500">
                <div>{t("Subtotal")} {cur()}{inr2(taxable)} · {loc.tax_label} {cur()}{inr2(gstAmt)}</div>
                {discOpen ? (
                  <span className="mt-1 flex items-center gap-1">
                    <input autoFocus className={inputCls + " !w-24 !py-0.5 text-xs"} placeholder={translate(`${cur()}`)} inputMode="numeric"
                      value={discount} onChange={(e) => setDiscount(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && applyDiscount()} />
                    <Button variant="outline" className="!px-2 !py-0.5 text-xs" disabled={busy} onClick={applyDiscount}>{translate("OK")}</Button>
                  </span>
                ) : (
                  <button type="button" onClick={() => setDiscOpen(true)}
                    className="mt-0.5 inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                    <Tag className="size-3" />
                    {(selected && detail ? detail.discount_amount : disc) > 0
                      ? `−${cur()}${inr(selected && detail ? detail.discount_amount : disc)}`
                      : t("Discount")}
                  </button>
                )}
              </div>
              <div className="text-right">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{t("Total")}</div>
                <div className="text-[1.65rem] font-bold tabular-nums leading-none text-zinc-900">{cur()}{inr2(grand)}</div>
              </div>
            </div>

            {ncOpen && selected && (
              <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 p-2">
                <p className="mb-1 text-xs font-medium text-amber-800">{t("Complimentary (no charge) - who authorized?")}</p>
                <div className="flex gap-1">
                  <select className={inputCls + " !w-28 !py-1 text-xs"} value={ncBy} onChange={(e) => setNcBy(e.target.value)}>
                    {["Captain", "Chef", "Manager", "GM", "Management", "Owner"].map((w) => <option key={w} value={w}>{translate(w)}</option>)}
                  </select>
                  <input autoFocus className={inputCls + " !py-1 text-xs"} placeholder={t("Reference (birthday, complaint #, promo…)")}
                    value={ncNote} onChange={(e) => setNcNote(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveNc()} />
                  <Button variant="outline" className="!px-2 !py-1 text-xs font-semibold text-amber-700" disabled={busy} onClick={() => saveNc()}>{translate("NC")}</Button>
                  <Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => setNcOpen(false)}>✕</Button>
                </div>
              </div>
            )}

            {cancelling && selected && detail && (
              <div className="mb-2">
                <VoidApproval outlet={outlet} busy={busy}
                  title={t("Cancel this bill")}
                  kitchenCount={detail.kitchen_lines ?? 0}
                  canApprove={!!detail.can_approve}
                  confirmLabel={t("Cancel bill")}
                  onConfirm={confirmCancel} onClose={() => setCancelling(false)} />
              </div>
            )}

            <div className="relative flex gap-1.5">
              <button type="button" onClick={() => setBillMenuOpen((v) => !v)}
                className="grid size-11 shrink-0 place-items-center rounded-xl border border-zinc-300 text-zinc-600 hover:bg-zinc-50"
                aria-label={t("Bill actions")} aria-expanded={billMenuOpen}>
                <MoreVertical className="size-5" />
              </button>
              {billMenuOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setBillMenuOpen(false)} aria-hidden />
                  <div className="absolute bottom-full left-0 z-20 mb-1 w-56 overflow-hidden rounded-xl border border-zinc-200 bg-white py-1 shadow-lg">
                    <button type="button" disabled={busy || !selected}
                      onClick={() => { setBillMenuOpen(false); printBill() }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-40">
                      <Receipt className="size-4 text-zinc-500" />{t("Print bill")}
                    </button>
                    <button type="button"
                      disabled={busy || !selected || !detail || detail.items.filter((i) => !i.voided).length < 2 || detail.status === "Delivered"}
                      onClick={() => { setBillMenuOpen(false); setSplitMode(true); setSplitSel(new Set()) }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-40">
                      <Scissors className="size-4 text-zinc-500" />{t("Split")}
                    </button>
                    <button type="button"
                      disabled={busy || !selected || !detail || detail.status === "Delivered"}
                      onClick={() => { setBillMenuOpen(false); detail?.nc ? saveNc(true) : setNcOpen(true) }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-amber-800 hover:bg-amber-50 disabled:opacity-40">
                      <Gift className="size-4" />{detail?.nc ? t("Undo NC") : t("Complimentary")}
                    </button>
                    <button type="button" disabled={busy || !!selected || cart.length === 0}
                      onClick={() => { setBillMenuOpen(false); hold() }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-40">
                      <PauseCircle className="size-4 text-zinc-500" />{t("Hold bill")}
                    </button>
                    <button type="button" disabled={busy || !selected || !detail?.kot_no}
                      onClick={() => { setBillMenuOpen(false); reprintKot() }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-40">
                      <Printer className="size-4 text-zinc-500" />{t("Reprint KOT")}
                    </button>
                    <button type="button"
                      disabled={busy || !selected || !detail || detail.status === "Delivered" || detail.status === "Cancelled"}
                      onClick={() => { setBillMenuOpen(false); setCancelling(true); setVoiding(null); setSettling(false) }}
                      className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-rose-600 hover:bg-rose-50 disabled:opacity-40">
                      <Ban className="size-4" />{t("Cancel")}
                    </button>
                  </div>
                </>
              )}
              <Button variant="outline"
                className="h-11 flex-1 border-brand-300 bg-brand-50 text-sm font-semibold text-brand-800 hover:bg-brand-100"
                disabled={busy || cart.length === 0}
                onClick={kotAction}>
                <Send className="size-4" />
                {selected ? t("KOT") : autoKot ? t("Send & print") : t("KOT")}
              </Button>
              <Button className="h-11 flex-[1.35] text-sm font-semibold"
                disabled={busy || (selected ? !detail : cart.length === 0)}
                onClick={proceedToPay}>
                <Wallet className="size-4" />
                {t("Settle")}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {billsPopupOpen && (
        <OpenBillsPopup
          open={open}
          selected={selected}
          detailLabel={detail ? orderLabel(detail) : selected || ""}
          detailStatus={detail?.status || ""}
          detailKot={detail?.kot_no ?? null}
          detailNc={!!detail?.nc}
          lines={detail?.items || []}
          grand={grand}
          busy={busy}
          onSelect={(name) => void openTab(name, { popup: true })}
          onSettle={() => { setBillsPopupOpen(false); void proceedToPay() }}
          onClose={() => setBillsPopupOpen(false)}
          onRemove={(row) => void removeLine(row)}
          onVoid={(row) => {
            const it = detail?.items.find((i) => i.row === row)
            if (it) { setVoiding(it); setCancelling(false); setBillsPopupOpen(false) }
          }}
        />
      )}

      {settling && selected && detail && (
        <SettleSheet
          subtitle={translate(orderLabel(detail))}
          grandLabel={`${cur()}${inr2(grand)}`}
          zeroLabel={`${cur()}0`}
          modes={posModes}
          busy={busy}
          nc={!!detail.nc}
          room={detail.room}
          rooms={rooms}
          postRoom={postRoom}
          onPostRoom={setPostRoom}
          onLoadRooms={loadRooms}
          sheetNc={sheetNc}
          ncBy={ncBy}
          ncNote={ncNote}
          onNcBy={setNcBy}
          onNcNote={setNcNote}
          onSheetNc={setSheetNc}
          onSettle={settle}
          onSettleDeliver={settleDeliver}
          onChargeToRoom={chargeToRoom}
          onSettleNc={settleNc}
          onClose={() => { setSettling(false); setSheetNc(false) }}
        />
      )}

      {/* phone: the bill's essentials ride along on the other panes */}
      {mobilePane !== "bill" && (cart.length > 0 || selected) && (
        <div className="sticky bottom-2 z-30 flex shrink-0 items-center gap-2 rounded-xl border border-brand-200 bg-white p-2 shadow-lg md:hidden">
          <button type="button" onClick={() => setMobilePane("bill")} className="min-w-0 flex-1 text-left">
            <div className="truncate text-[10px] font-semibold uppercase tracking-wide text-brand-700">
              {cart.length > 0
                ? `+ ${cart[0].item_name}${cart[0].qty > 1 ? ` ×${cart[0].qty}` : ""}`
                : translate("{v0} item{v1}{v2}", { v0: String(Math.round(billItemCount)), v1: String(billItemCount === 1 ? "" : "s"), v2: String(selected && detail ? ` · ${orderLabel(detail)}` : "") })}
            </div>
            <div className="text-lg font-bold tabular-nums">{cur()}{inr2(grand)}</div>
          </button>
          <Button variant="outline" className="h-11" onClick={() => setMobilePane("bill")}>{t("View bill")}</Button>
          <Button className="h-11" disabled={busy || (selected ? !detail : cart.length === 0)} onClick={proceedToPay}>
            <Wallet className="size-4" />{t("Settle")}
          </Button>
        </div>
      )}

      {/* tables drawer - desktop/tablet; phones use the Tables pane */}
      {tablesOpen && (
        <div className="fixed inset-0 z-40 hidden md:block">
          <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={() => setTablesOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[22rem] flex-col gap-2 overflow-y-auto border-e border-zinc-200 bg-zinc-50 p-3 shadow-2xl animate-sheet-in xl:w-[24rem]">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-zinc-700">{t("Tables & running bills")}</h2>
              <button className="rounded-md p-1.5 text-zinc-400 hover:text-zinc-700" aria-label={t("Close")}
                onClick={() => setTablesOpen(false)}>
                <XCircle className="size-4" />
              </button>
            </div>
            {tablesPane}
          </div>
        </div>
      )}

      {/* every past bill, on a wide screen of its own */}
      {historyOpen && outlet && (
        <OrderHistory outlet={outlet} onClose={() => setHistoryOpen(false)}
          onOpenBill={(n) => { setHistoryOpen(false); void openTab(n) }} />
      )}

      {/* orders list and who the bill is for, over the till */}
      {panel && outlet && (
        <PosSidePanel outlet={outlet} tab={panel} onTab={setPanel}
          onClose={() => setPanel(null)} refreshKey={panelKey}
          order={selected}
          draft={{
            room: !selected && (orderType === "Room Service" || orderType === "Dine In") ? room || null : null,
            guest: !selected ? draftGuest?.guest ?? null : null,
          }}
          onDraftGuest={(g) => setDraftGuest(g)}
          onOpenBill={(n) => { setPanel(null); void openTab(n) }}
          onHistory={() => { setPanel(null); setHistoryOpen(true) }}
          onGuestChanged={() => { void reloadDetail().catch(() => {}); loadOpen() }} />
      )}
    </div>
  )
}

/** "101 · Guest Name" for every in-house room; refreshes when opened. */
function RoomPicker({ rooms, value, onChange, onOpen, placeholder }: {
  rooms: InHouseRoom[]; value: string; onChange: (room: string) => void
  onOpen: () => void; placeholder: string
}) {
  const { t } = useT()
  return (
    <select className={inputCls} value={value} onFocus={onOpen}
      onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder}</option>
      {rooms.map((r) => {
        // the check-in blocked charges to this room: shown, not chargeable
        const blocked = Number(r.room_charges_allowed ?? 1) === 0
        return (
          <option key={r.room} value={r.room} disabled={blocked}>
            {r.room_number}{r.guest_name ? ` · ${r.guest_name}` : ""}{blocked ? ` (${t("no room charges")})` : ""}
          </option>
        )
      })}
    </select>
  )
}

function RunningStrip({
  open, selected, onOpen, onSeeAll,
}: {
  open: OpenOrder[]
  selected: string | null
  onOpen: (name: string) => void
  onSeeAll: () => void
}) {
  const { t } = useT()
  if (!open.length) return null
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-0.5">
      <button type="button" onClick={onSeeAll}
        className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-dashed border-brand-400 bg-brand-50 px-2.5 text-xs font-bold text-brand-800 hover:border-brand-500"
        title={t("See all open bills")}>
        <Maximize2 className="size-3.5" />
        {t("All")} · {open.length}
      </button>
      {open.map((o) => {
        const tone = !o.kot_fired
          ? (o.stale ? "border-rose-400 bg-rose-50 text-rose-950" : "border-amber-400 bg-amber-50 text-amber-950")
          : o.pending > 0
            ? "border-sky-400 bg-sky-50 text-sky-950"
            : "border-emerald-400 bg-emerald-50 text-emerald-950"
        const tag = !o.kot_fired ? ago(o.creation)
          : o.pending > 0 ? t("In kitchen") : t("Ready / unpaid")
        return (
          <button key={o.name} type="button" onClick={() => onOpen(o.name)}
            className={"inline-flex h-9 max-w-[11rem] shrink-0 items-center gap-2 rounded-lg border px-2.5 text-left " + tone +
              (selected === o.name ? " ring-2 ring-brand-600 ring-offset-1" : "")}>
            <span className="min-w-0 truncate text-xs font-bold">{translate(o.label)}</span>
            <span className="shrink-0 text-[10px] font-semibold tabular-nums opacity-80">
              {cur()}{inr(o.order_total)}
            </span>
            <span className="hidden shrink-0 text-[10px] font-bold uppercase tracking-wide opacity-70 sm:inline">{tag}</span>
          </button>
        )
      })}
    </div>
  )
}

/** The Indian FSSAI mark: green dot in a square = veg, maroon triangle =
 *  non-veg. Shape carries it, so it survives colour-blindness and sun glare. */
function VegMark({ veg }: { veg: number }) {
  const { t } = useT()
  return (
    <span aria-label={(veg ? t("Veg") : t("Non-veg"))}
      className={"grid size-3.5 shrink-0 place-items-center rounded-[3px] border-2 " +
        (veg ? "border-emerald-600" : "border-rose-700")}>
      {veg ? (
        <span className="size-1 rounded-full bg-emerald-600" />
      ) : (
        <span className="size-0 border-x-[2.5px] border-b-[4px] border-x-transparent border-b-rose-700" />
      )}
    </span>
  )
}

function MenuCard({ it, onAdd }: { it: MenuItem; onAdd: () => void }) {
  return (
    <button type="button" onClick={onAdd}
      className="group flex min-h-[5rem] flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white text-left shadow-sm transition hover:border-brand-500 hover:shadow-md active:scale-[0.98]">
      {it.image && <img src={it.image} alt="" className="h-20 w-full object-cover" />}
      <div className="flex flex-1 flex-col justify-between gap-1.5 p-2.5">
        <div className="flex items-start gap-1.5">
          <VegMark veg={it.is_veg} />
          <span className="line-clamp-2 text-sm font-semibold leading-snug text-zinc-900">{it.item_name}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-bold tabular-nums text-zinc-800">{cur()}{inr(it.price)}</span>
          <span className="grid size-8 place-items-center rounded-full bg-brand-50 text-brand-700 transition group-hover:bg-brand-600 group-hover:text-white">
            <Plus className="size-3.5" />
          </span>
        </div>
      </div>
    </button>
  )
}
