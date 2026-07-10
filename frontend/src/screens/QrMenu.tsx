import { useCallback, useEffect, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { Plus, Minus, Leaf, ShoppingBag } from "lucide-react"
import { call } from "../lib/api"
import { accentVars } from "../lib/accents"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

interface MenuItem {
  name: string
  item_name: string
  category: string
  price: number
  is_veg: number
  is_alcohol: number
  image: string | null
  description: string | null
}
interface Menu {
  outlet: string
  outlet_name: string
  property_name: string
  categories: { category: string; items: MenuItem[] }[]
}

/** Guest-facing digital menu behind a table/room QR code. */
export default function QrMenu() {
  const { outlet = "" } = useParams()
  const [params] = useSearchParams()
  const room = params.get("room") || ""
  const table = params.get("table") || ""
  const [menu, setMenu] = useState<Menu | null>(null)
  const [cart, setCart] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    call<Menu>("kamra.public_api.qr_menu", { outlet })
      .then(setMenu)
      .catch((e) => setError((e as Error).message))
  }, [outlet])
  useEffect(load, [load])

  const flat = menu?.categories.flatMap((c) => c.items) ?? []
  const qty = (mi: string) => cart[mi] || 0
  const set = (mi: string, d: number) =>
    setCart((c) => {
      const n = Math.max(0, (c[mi] || 0) + d)
      const next = { ...c }
      if (n === 0) delete next[mi]
      else next[mi] = n
      return next
    })
  const total = flat.reduce((s, it) => s + qty(it.name) * it.price, 0)
  const count = Object.values(cart).reduce((s, n) => s + n, 0)

  async function order() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<{ order: string; message: string }>("kamra.public_api.qr_order", {
        outlet,
        room: room || null,
        table_no: table || null,
        items: Object.entries(cart).map(([menu_item, q]) => ({ menu_item, qty: q })),
      })
      setDone(r.message)
      setCart({})
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !menu)
    return <div className="mx-auto max-w-lg p-8 text-center text-zinc-500">{error}</div>
  if (!menu)
    return <div className="p-10 text-center text-zinc-400">Loading menu…</div>

  return (
    <div className="min-h-screen bg-zinc-50 pb-28" style={accentVars("Emerald")}>
      <header className="border-b border-zinc-200 bg-white px-4 py-4">
        <h1 className="text-lg font-bold text-zinc-800">{menu.outlet_name}</h1>
        <p className="text-xs text-zinc-500">
          {menu.property_name}
          {room ? ` · Room ${room.split("-").pop()}` : table ? ` · Table ${table}` : ""}
        </p>
      </header>

      {done ? (
        <div className="mx-auto max-w-lg p-8 text-center">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-800">
            <ShoppingBag className="mx-auto mb-2 size-8" />
            <p className="font-medium">{done}</p>
          </div>
          <button className="mt-4 text-sm font-medium text-brand-700" onClick={() => setDone(null)}>
            Order more
          </button>
        </div>
      ) : (
        <main className="mx-auto max-w-lg px-3 py-3">
          {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          {menu.categories.map((c) => (
            <section key={c.category} className="mb-5">
              <h2 className="mb-2 px-1 text-sm font-semibold uppercase tracking-wide text-zinc-500">{c.category}</h2>
              <div className="space-y-2">
                {c.items.map((it) => (
                  <div key={it.name} className="flex gap-3 rounded-xl border border-zinc-200 bg-white p-2.5">
                    {it.image && <img src={it.image} alt="" className="size-16 shrink-0 rounded-lg object-cover" />}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <Leaf className={"size-3 " + (it.is_veg ? "text-emerald-600" : "text-rose-500")} />
                        <span className="text-sm font-medium">{it.item_name}</span>
                      </div>
                      {it.description && <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500">{it.description}</p>}
                      <div className="mt-1 text-sm font-semibold">₹{inr(it.price)}</div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5 self-center">
                      {qty(it.name) > 0 && (
                        <>
                          <button onClick={() => set(it.name, -1)} className="size-8 rounded-lg border border-zinc-300"><Minus className="mx-auto size-4" /></button>
                          <span className="w-5 text-center text-sm tabular-nums">{qty(it.name)}</span>
                        </>
                      )}
                      <button onClick={() => set(it.name, 1)} className="size-8 rounded-lg bg-brand-600 text-white"><Plus className="mx-auto size-4" /></button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </main>
      )}

      {!done && count > 0 && (
        <div className="fixed inset-x-0 bottom-0 border-t border-zinc-200 bg-white p-3">
          <button disabled={busy} onClick={order}
            className="mx-auto flex w-full max-w-lg items-center justify-between rounded-xl bg-brand-600 px-4 py-3 font-semibold text-white disabled:opacity-60">
            <span>{count} item{count === 1 ? "" : "s"}</span>
            <span>Place order · ₹{inr(total)}</span>
          </button>
          <p className="mx-auto mt-1 max-w-lg text-center text-[11px] text-zinc-400">
            A server confirms your order before the kitchen starts.
          </p>
        </div>
      )}
    </div>
  )
}
