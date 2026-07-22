import { useCallback, useEffect, useState } from "react"
import { Zap } from "lucide-react"
import { call } from "../../lib/api"
import { subscribeRealtime } from "../../lib/realtime"
import { serverError } from "../../lib/resource"
import { cn } from "../../lib/utils"

/** Shared laundry types, helpers and data hook used by BOTH the housekeeping
 * phone app (HkLaundry) and the desktop Laundry module. Keep the pricing and
 * lifecycle logic here so the two surfaces never diverge. */

export interface Rate {
  name: string
  item_name: string
  service_type: string
  rate: number
  express_rate: number
}
export interface LaundryItem {
  name: string
  item_name: string
  service_type: string
  qty: number
  returned_qty: number
  rate: number
  amount: number
}
export interface LaundryOrder {
  name: string
  room: string
  room_no: string
  guest_name: string | null
  status: string
  express: number
  total: number
  notes: string | null
  pieces: number
  pending: number
  shortage_note: string | null
  posted_to_folio: number
  order_type?: string
  complimentary?: number
  house_label?: string | null
  ready_by?: string | null
  overdue?: boolean
  items: LaundryItem[]
}
export interface Room {
  name: string
  room_number: string
  occupancy_status?: string
}
export interface Board {
  open: LaundryOrder[]
  recent: LaundryOrder[]
}

export const STATUS_TONE: Record<
  string,
  "zinc" | "amber" | "sky" | "green" | "rose"
> = {
  Requested: "rose",
  Collected: "amber",
  "In Process": "sky",
  Ready: "green",
  Delivered: "zinc",
  Cancelled: "zinc",
}

export const LAUNDRY_SERVICES = ["Wash & Iron", "Dry Clean", "Iron Only"]

export const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

/** One item line as the backend expects it for collect_laundry. */
export interface CollectLine {
  item_name: string
  service_type: string
  qty: number
}

// --- backend calls (single source of truth for the wire contract) -----------

export type OrderType = "Guest" | "House"

export const laundryApi = {
  requestPickup: (
    property: string,
    room: string,
    notes: string | null,
    express: boolean,
    orderType: OrderType = "Guest",
    houseLabel: string | null = null,
  ) =>
    call("kamra.laundry.request_pickup", {
      property,
      room: room || null,
      notes: notes || null,
      express: express ? 1 : 0,
      order_type: orderType,
      house_label: houseLabel || null,
    }),

  collect: (
    property: string,
    room: string,
    items: CollectLine[],
    order: string | null,
    express: boolean,
    orderType: OrderType = "Guest",
    houseLabel: string | null = null,
    complimentary = false,
  ) =>
    call("kamra.laundry.collect_laundry", {
      property,
      room: room || null,
      items,
      order,
      express: express ? 1 : 0,
      order_type: orderType,
      house_label: houseLabel || null,
      complimentary: complimentary ? 1 : 0,
    }),

  setStatus: (order: string, status: string) =>
    call("kamra.laundry.laundry_status", { order, status }),

  returnItems: (order: string, rows: Record<string, number>) =>
    call("kamra.laundry.return_items", { order, rows }),

  deliver: (order: string, shortageNote: string | null) =>
    call("kamra.laundry.deliver_laundry", { order, shortage_note: shortageNote }),

  cancel: (order: string, reason: string) =>
    call("kamra.laundry.cancel_laundry", { order, reason }),
}

/**
 * Owns the laundry board + rate card for a property: initial load, a 20s poll,
 * and realtime refresh. `act` wraps a mutation with busy/error handling and
 * reloads on success. Extracted verbatim from HkLaundry so both surfaces share
 * the same data lifecycle.
 */
export function useLaundryBoard(property: string) {
  const [board, setBoard] = useState<Board | null>(null)
  const [rates, setRates] = useState<Rate[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(() => {
    call<Board>("kamra.laundry.laundry_board", { property })
      .then(setBoard)
      .catch((e) => setError(serverError(e)))
    call<Rate[]>("kamra.laundry.laundry_rates", { property })
      .then(setRates)
      .catch(() => {})
  }, [property])

  useEffect(() => {
    reload()
    const unsub = subscribeRealtime(reload)
    const t = setInterval(reload, 20_000)
    return () => {
      unsub()
      clearInterval(t)
    }
  }, [reload])

  const act = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true)
      setError(null)
      try {
        await fn()
        reload()
      } catch (e) {
        setError(serverError(e))
      } finally {
        setBusy(false)
      }
    },
    [reload],
  )

  return { board, rates, error, setError, busy, act, reload }
}

export function ExpressToggle({
  value,
  onChange,
}: {
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center justify-center gap-1.5 rounded-xl border py-2.5 text-sm font-semibold",
        value
          ? "border-amber-400 bg-amber-50 text-amber-700"
          : "border-zinc-300 text-zinc-500",
      )}
      onClick={() => onChange(!value)}
    >
      <Zap className="size-4" />
      {value ? "Express — same day (higher rate)" : "Standard service"}
    </button>
  )
}
