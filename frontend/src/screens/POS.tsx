import { useCallback, useEffect, useRef, useState } from "react"
import {
  Plus, Minus, Trash2, Send, UtensilsCrossed, Leaf, Search,
  Maximize2, Minimize2, Wallet,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
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
  kot_fired: number
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
}
interface Detail {
  name: string
  status: string
  table_no: string | null
  room: string | null
  discount_amount: number
  subtotal: number
  order_total: number
  items: OrderItem[]
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
  const [selected, setSelected] = useState<string | null>(null) // null = new order
  const [detail, setDetail] = useState<Detail | null>(null)
  const [room, setRoom] = useState("")
  const [table, setTable] = useState("")
  const [cart, setCart] = useState<CartLine[]>([]) // new lines (new order OR next round)
  const [discount, setDiscount] = useState("")
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

  const loadMenu = useCallback(() => {
    if (!outlet) return
    call<{ categories: { category: string; items: MenuItem[] }[] }>("kamra.pos.pos_menu", { outlet })
      .then((m) => setCats(m.categories)).catch((e) => setError(serverError(e)))
  }, [outlet])
  useEffect(loadMenu, [loadMenu])

  const loadOpen = useCallback(() => {
    if (!outlet) return
    call<OpenOrder[]>("kamra.pos.open_orders", { outlet }).then(setOpen).catch(() => {})
  }, [outlet])
  useEffect(() => {
    loadOpen()
    const t = setInterval(loadOpen, 15_000)
    return () => clearInterval(t)
  }, [loadOpen])

  function newOrder() {
    setSelected(null); setDetail(null); setCart([]); setRoom(""); setTable("")
  }
  async function openTab(name: string) {
    setSelected(name); setCart([])
    const d = await call<Detail>("kamra.pos.order_detail", { order: name })
    setDetail(d)
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

  async function sendNew() {
    await act(async () => {
      const r = await call<{ order: string }>("kamra.pos.create_order", {
        outlet, property: getCurrentProperty(), room: room || null, table_no: table || null,
        items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
      })
      if (disc > 0) await call("kamra.pos.apply_discount", { order: r.order, amount: disc, reason: "" })
      await call("kamra.pos.confirm_order", { order: r.order })
      await call("kamra.pos.fire_kot", { order: r.order })
      newOrder()
      setDiscount("")
    })
  }
  async function addRound() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.add_items", {
        order: selected,
        items: cart.map((l) => ({ menu_item: l.menu_item, qty: l.qty, instructions: l.instructions })),
      })
      await call("kamra.pos.fire_kot", { order: selected })
      const d = await call<Detail>("kamra.pos.order_detail", { order: selected })
      setDetail(d); setCart([])
    })
  }
  async function deliver() {
    if (!selected) return
    await act(async () => {
      await call("kamra.pos.deliver_order", { order: selected })
      newOrder()
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
            <select className={inputCls + " !w-auto"} value={outlet} onChange={(e) => { setOutlet(e.target.value); newOrder() }}>
              {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
            </select>
            <button onClick={toggleFull} className="rounded-lg border border-zinc-300 bg-white p-2 text-zinc-600 hover:bg-zinc-50" title="Full screen">
              {full ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </button>
          </div>
        </div>

        {/* running tabs - juggle several tables at once */}
        <div className="flex flex-wrap gap-2">
          <button onClick={newOrder}
            className={"inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm font-medium " +
              (selected === null ? "border-brand-600 bg-brand-600 text-white" : "border-dashed border-zinc-300 text-zinc-600 hover:border-brand-400")}>
            <Plus className="size-4" />New order
          </button>
          {open.map((o) => (
            <button key={o.name} onClick={() => openTab(o.name)}
              className={"inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm " +
                (selected === o.name ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-zinc-200 bg-white hover:border-brand-400")}>
              {o.label}
              <span className="text-xs text-zinc-400">₹{inr(o.order_total)}</span>
            </button>
          ))}
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
                  <h2 className="font-semibold">{detail.table_no ? `Table ${detail.table_no}` : detail.room ? `Room ${detail.room.split("-").pop()}` : detail.name}</h2>
                  <span className="text-xs text-zinc-400">{detail.status}</span>
                </div>
                <ul className="mb-2 space-y-1 border-b border-zinc-100 pb-2 text-sm">
                  {detail.items.map((it) => (
                    <li key={it.row} className="flex justify-between">
                      <span>{Math.round(it.qty)}× {it.item_name}
                        {it.kot_status !== "New" && <span className="ml-1 text-[10px] text-zinc-400">{it.kot_status}</span>}
                      </span>
                      <span className="tabular-nums">₹{inr(it.amount)}</span>
                    </li>
                  ))}
                </ul>
                <div className="mb-2 flex justify-between text-sm font-semibold"><span>Running total</span><span>₹{inr(detail.order_total)}</span></div>
              </>
            ) : (
              <div className="mb-3 grid grid-cols-2 gap-2">
                <select className={inputCls} value={room} onChange={(e) => setRoom(e.target.value)}>
                  <option value="">Room…</option>
                  {rooms.map((r) => <option key={r.name} value={r.name}>Room {r.room_number}</option>)}
                </select>
                <input className={inputCls} placeholder="Table" value={table} onChange={(e) => setTable(e.target.value)} />
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
              {selected ? (
                <>
                  <Button className="w-full" disabled={busy || cart.length === 0} onClick={addRound}>
                    <Send className="size-4" />Add round & fire KOT
                  </Button>
                  <Button variant="outline" className="w-full" disabled={busy} onClick={deliver}>
                    <Wallet className="size-4" />Deliver & post to bill
                  </Button>
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
