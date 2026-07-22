import { useMemo, useState } from "react"
import { Shirt, Zap, Plus, Minus, ChevronRight } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { Badge } from "../components/ui/badge"
import { cn } from "../lib/utils"
import {
  ExpressToggle,
  inr,
  STATUS_TONE,
  useLaundryBoard,
  type LaundryOrder,
  type Room,
} from "./laundry/shared"

/** The laundry side of the housekeeping phone app: pickup queue, counting
 * the bag with the guest, tracking what's out, and returning it piece by
 * piece. Prices always come from the property's rate card. Types, the rate
 * card / board data hook and helpers are shared with the desktop Laundry
 * module (see ./laundry/shared). */

export default function HkLaundry({ rooms }: { rooms: Room[] }) {
  const property = getCurrentProperty()
  const { board, rates, error, busy, act } = useLaundryBoard(property)
  // sheets
  const [pickup, setPickup] = useState<{ room: string; notes: string; express: boolean } | null>(null)
  const [counting, setCounting] = useState<{ order: string | null; room: string; express: boolean; qty: Record<string, number> } | null>(null)
  const [returning, setReturning] = useState<{ order: LaundryOrder; back: Record<string, number>; note: string } | null>(null)

  const occupied = useMemo(
    () => rooms.filter((r) => r.occupancy_status === "Occupied"),
    [rooms])

  const countTotal = counting
    ? rates.reduce((s, r) => s + (counting.qty[r.name] || 0) *
        (counting.express ? r.express_rate : r.rate), 0)
    : 0
  const countPieces = counting
    ? Object.values(counting.qty).reduce((s, q) => s + q, 0) : 0

  async function submitCollect() {
    if (!counting || countPieces === 0) return
    const items = rates
      .filter((r) => (counting.qty[r.name] || 0) > 0)
      .map((r) => ({ item_name: r.item_name, service_type: r.service_type, qty: counting.qty[r.name] }))
    await act(async () => {
      await call("kamra.laundry.collect_laundry", {
        property, room: counting.room, items,
        order: counting.order, express: counting.express ? 1 : 0,
      })
      setCounting(null)
    })
  }

  const returnPending = returning
    ? returning.order.items.reduce(
        (s, it) => s + it.qty - (returning.back[it.name] ?? it.returned_qty), 0)
    : 0

  async function submitDeliver() {
    if (!returning) return
    const r = returning
    await act(async () => {
      await call("kamra.laundry.return_items", {
        order: r.order.name,
        rows: Object.fromEntries(r.order.items.map((it) => [it.name, r.back[it.name] ?? it.returned_qty])),
      })
      await call("kamra.laundry.deliver_laundry", {
        order: r.order.name,
        shortage_note: returnPending > 0 ? r.note : null,
      })
      setReturning(null)
    })
  }

  const OrderCard = ({ o }: { o: LaundryOrder }) => (
    <li className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold tabular-nums">{o.room_no}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{o.guest_name || o.name}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={STATUS_TONE[o.status] || "zinc"}>{o.status}</Badge>
            {!!o.express && <Badge tone="amber"><Zap className="mr-0.5 size-3" />express</Badge>}
            {o.pieces > 0 && <Badge tone="zinc">{o.pieces} pc</Badge>}
            {o.pending > 0 && o.status !== "Requested" && (
              <Badge tone="rose">{o.pending} pending</Badge>
            )}
          </div>
        </div>
        {o.total > 0 && <span className="text-sm font-semibold tabular-nums">₹{inr(o.total)}</span>}
      </div>
      {o.notes && <p className="mt-2 text-sm text-zinc-500">{o.notes}</p>}
      {o.shortage_note && (
        <p className="mt-2 rounded-lg bg-rose-50 px-2.5 py-1.5 text-sm text-rose-700">
          Shortage: {o.shortage_note}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        {o.status === "Requested" && (
          <button
            className="flex-1 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white"
            disabled={busy}
            onClick={() => setCounting({ order: o.name, room: o.room, express: !!o.express, qty: {} })}>
            Collect & count
          </button>
        )}
        {o.status === "Collected" && (
          <button
            className="flex-1 rounded-xl bg-sky-600 py-2.5 text-sm font-semibold text-white"
            disabled={busy}
            onClick={() => act(() => call("kamra.laundry.laundry_status", { order: o.name, status: "In Process" }))}>
            Send to laundry
          </button>
        )}
        {o.status === "In Process" && (
          <button
            className="flex-1 rounded-xl bg-emerald-600 py-2.5 text-sm font-semibold text-white"
            disabled={busy}
            onClick={() => act(() => call("kamra.laundry.laundry_status", { order: o.name, status: "Ready" }))}>
            Mark ready
          </button>
        )}
        {["Collected", "In Process", "Ready"].includes(o.status) && (
          <button
            className={cn("flex-1 rounded-xl border py-2.5 text-sm font-semibold",
              o.status === "Ready" ? "border-brand-600 text-brand-700" : "border-zinc-300 text-zinc-600")}
            disabled={busy}
            onClick={() => setReturning({ order: o, back: {}, note: "" })}>
            Return & deliver
          </button>
        )}
      </div>
    </li>
  )

  const open = board?.open ?? []
  const requested = open.filter((o) => o.status === "Requested")
  const inHand = open.filter((o) => o.status !== "Requested")

  return (
    <div className="space-y-4">
      {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <div className="grid grid-cols-2 gap-2">
        <button
          className="rounded-xl border border-zinc-300 bg-white py-3 text-sm font-semibold text-zinc-700"
          onClick={() => setPickup({ room: "", notes: "", express: false })}>
          Log pickup request
        </button>
        <button
          className="rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white"
          onClick={() => setCounting({ order: null, room: "", express: false, qty: {} })}>
          <Shirt className="mr-1 inline size-4" />Collect now
        </button>
      </div>

      {requested.length > 0 && (
        <>
          <p className="px-1 text-sm font-medium text-zinc-500">Pickup requests</p>
          <ul className="space-y-3">{requested.map((o) => <OrderCard key={o.name} o={o} />)}</ul>
        </>
      )}

      <p className="px-1 text-sm font-medium text-zinc-500">
        In hand ({inHand.length})
      </p>
      <ul className="space-y-3">
        {inHand.map((o) => <OrderCard key={o.name} o={o} />)}
        {inHand.length === 0 && (
          <li className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-zinc-400">
            No laundry out right now.
          </li>
        )}
      </ul>

      {(board?.recent ?? []).length > 0 && (
        <>
          <p className="px-1 text-sm font-medium text-zinc-500">Recent</p>
          <ul className="space-y-1">
            {(board?.recent ?? []).map((o) => (
              <li key={o.name} className="flex items-center justify-between rounded-xl bg-white px-3 py-2 text-sm">
                <span className="text-zinc-600">
                  {o.room_no} · {o.guest_name || o.name}
                  {o.shortage_note && <span className="ml-1 text-rose-500">!</span>}
                </span>
                <span className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[o.status] || "zinc"}>{o.status}</Badge>
                  {o.total > 0 && <span className="tabular-nums font-medium">₹{inr(o.total)}</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* pickup request sheet */}
      {pickup && (
        <Sheet onClose={() => setPickup(null)} title="Laundry pickup request">
          <select
            className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
            value={pickup.room}
            onChange={(e) => setPickup({ ...pickup, room: e.target.value })}>
            <option value="">Room…</option>
            {occupied.map((r) => <option key={r.name} value={r.name}>Room {r.room_number}</option>)}
          </select>
          <input
            className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
            placeholder="Notes (bag on door, after 3pm…)"
            value={pickup.notes}
            onChange={(e) => setPickup({ ...pickup, notes: e.target.value })} />
          <ExpressToggle value={pickup.express} onChange={(v) => setPickup({ ...pickup, express: v })} />
          <button
            className="w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white disabled:opacity-50"
            disabled={busy || !pickup.room}
            onClick={() => act(async () => {
              await call("kamra.laundry.request_pickup", {
                property, room: pickup.room, notes: pickup.notes || null,
                express: pickup.express ? 1 : 0,
              })
              setPickup(null)
            })}>
            Add to pickup queue
          </button>
        </Sheet>
      )}

      {/* count sheet */}
      {counting && (
        <Sheet onClose={() => setCounting(null)} title="Count the bag">
          {!counting.order && (
            <select
              className="w-full rounded-xl border border-zinc-300 px-3 py-3 text-base"
              value={counting.room}
              onChange={(e) => setCounting({ ...counting, room: e.target.value })}>
              <option value="">Room…</option>
              {occupied.map((r) => <option key={r.name} value={r.name}>Room {r.room_number}</option>)}
            </select>
          )}
          <ExpressToggle value={counting.express} onChange={(v) => setCounting({ ...counting, express: v })} />
          <div className="max-h-72 space-y-1 overflow-y-auto">
            {rates.map((r) => {
              const q = counting.qty[r.name] || 0
              const price = counting.express ? r.express_rate : r.rate
              return (
                <div key={r.name}
                  className={cn("flex items-center gap-2 rounded-xl border px-3 py-2",
                    q > 0 ? "border-brand-300 bg-brand-50" : "border-zinc-200")}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{r.item_name}</p>
                    <p className="text-xs text-zinc-400">{r.service_type} · ₹{inr(price)}</p>
                  </div>
                  <button className="rounded-lg border border-zinc-300 p-1.5" aria-label="less"
                    onClick={() => setCounting({ ...counting, qty: { ...counting.qty, [r.name]: Math.max(0, q - 1) } })}>
                    <Minus className="size-4" />
                  </button>
                  <span className="w-6 text-center text-base font-bold tabular-nums">{q}</span>
                  <button className="rounded-lg border border-zinc-300 p-1.5" aria-label="more"
                    onClick={() => setCounting({ ...counting, qty: { ...counting.qty, [r.name]: q + 1 } })}>
                    <Plus className="size-4" />
                  </button>
                </div>
              )
            })}
            {rates.length === 0 && (
              <p className="py-4 text-center text-sm text-zinc-400">
                No rate card yet — add laundry rates in Settings.
              </p>
            )}
          </div>
          <button
            className="w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white disabled:opacity-50"
            disabled={busy || countPieces === 0 || (!counting.order && !counting.room)}
            onClick={submitCollect}>
            Collect {countPieces} piece{countPieces === 1 ? "" : "s"} · ₹{inr(countTotal)}
          </button>
        </Sheet>
      )}

      {/* return & deliver sheet */}
      {returning && (
        <Sheet onClose={() => setReturning(null)} title={`Return to room ${returning.order.room_no}`}>
          <button
            className="w-full rounded-xl border border-emerald-300 bg-emerald-50 py-2.5 text-sm font-semibold text-emerald-700"
            onClick={() => setReturning({
              ...returning,
              back: Object.fromEntries(returning.order.items.map((it) => [it.name, it.qty])),
            })}>
            Everything came back
          </button>
          <div className="max-h-72 space-y-1 overflow-y-auto">
            {returning.order.items.map((it) => {
              const back = returning.back[it.name] ?? it.returned_qty
              return (
                <div key={it.name} className="flex items-center gap-2 rounded-xl border border-zinc-200 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{it.item_name}</p>
                    <p className="text-xs text-zinc-400">{it.service_type} · collected {it.qty}</p>
                  </div>
                  <button className="rounded-lg border border-zinc-300 p-1.5" aria-label="less"
                    onClick={() => setReturning({ ...returning, back: { ...returning.back, [it.name]: Math.max(0, back - 1) } })}>
                    <Minus className="size-4" />
                  </button>
                  <span className={cn("w-10 text-center text-base font-bold tabular-nums",
                    back < it.qty ? "text-rose-600" : "text-emerald-700")}>
                    {back}/{it.qty}
                  </span>
                  <button className="rounded-lg border border-zinc-300 p-1.5" aria-label="more"
                    onClick={() => setReturning({ ...returning, back: { ...returning.back, [it.name]: Math.min(it.qty, back + 1) } })}>
                    <Plus className="size-4" />
                  </button>
                </div>
              )
            })}
          </div>
          {returnPending > 0 && (
            <input
              className="w-full rounded-xl border border-rose-300 bg-rose-50 px-3 py-3 text-base"
              placeholder={`${returnPending} piece(s) short — why? (required)`}
              value={returning.note}
              onChange={(e) => setReturning({ ...returning, note: e.target.value })} />
          )}
          <button
            className="w-full rounded-xl bg-brand-600 py-3 text-base font-semibold text-white disabled:opacity-50"
            disabled={busy || (returnPending > 0 && !returning.note.trim())}
            onClick={submitDeliver}>
            <ChevronRight className="mr-1 inline size-4" />
            Deliver & bill ₹{inr(returning.order.total)}
            {returnPending > 0 ? ` (${returnPending} short)` : ""}
          </button>
        </Sheet>
      )}
    </div>
  )
}

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/40" onClick={onClose}>
      <div className="max-h-[90vh] w-full space-y-3 overflow-y-auto rounded-t-2xl bg-white p-4"
        onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  )
}
