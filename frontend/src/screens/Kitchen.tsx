import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  ChefHat, Check, RefreshCw, Clock, X, Undo2, TriangleAlert, Flame, Lock,
  Martini, CookingPot, Utensils, Bell, BellOff, Play, Inbox,
} from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { subscribeRealtime } from "../lib/realtime"
import { Button } from "../components/ui/button"
import { cn } from "../lib/utils"

type LineState = "cooking" | "held" | "cancelled" | "done"

interface KotItem {
  name: string
  item_name: string
  qty: number
  instructions: string | null
  kot_status: string
  state: LineState
  course: string
  is_veg: 0 | 1 | null
  is_alcohol: 0 | 1 | null
  prep_station: string | null
  allergens: string | null
  allergy_hits: string[]
  fired_at: string | null
  prepared_at: string | null
  void_reason: string | null
}
interface KotOrder {
  name: string
  outlet_name: string
  room_no: string
  table_no: string | null
  creation: string
  notes: string | null
  allergy_note: string | null
  kot_no: number | null
  order_type: string | null
  guests: number | null
  captain: string | null
  order_total: number | null
  accepted_at: string | null
  held_courses: string[]
  items: KotItem[]
}

// Mirrors pos.py: the order food is served in, and the stations a KOT prints to.
const COURSE_ORDER = ["Starter", "Main", "Dessert", "Drink"]
const STATIONS = ["Kitchen", "Tandoor", "Grill", "Fryer", "Bar"]
// The kitchen's own thresholds, in minutes: fresh, working, needs eyes.
const AMBER_AT = 5
const LATE_AT = 10
const CHIME_KEY = "kamra.kds.chime"

const STATION_ICON: Record<string, typeof Flame> = {
  Kitchen: ChefHat, Tandoor: Flame, Grill: Flame, Fryer: CookingPot, Bar: Martini,
}

function parse(iso: string): number {
  return new Date(iso.replace(" ", "T")).getTime()
}
function clockOf(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
}

/* The cook's clock starts when the course was FIRED, never when the captain
   opened the tab - a table that sat an hour over drinks must not hand the
   kitchen a ticket that is already red. Nothing cooking means no clock: a
   ticket waiting on the pass is the floor's problem, not the line's. */
function firedAgeSecs(o: KotOrder, now: number): number | null {
  const stamps = o.items
    .filter((i) => i.state === "cooking")
    .map((i) => parse(i.fired_at ?? o.creation))
  if (!stamps.length) return null
  return Math.max(0, Math.round((now - Math.min(...stamps)) / 1000))
}

function ageTone(secs: number | null) {
  if (secs === null) return { border: "border-zinc-200", text: "text-zinc-400", bar: "bg-zinc-200" }
  const m = secs / 60
  return m >= LATE_AT
    ? { border: "border-rose-400", text: "text-rose-600", bar: "bg-rose-500" }
    : m >= AMBER_AT
      ? { border: "border-amber-400", text: "text-amber-600", bar: "bg-amber-500" }
      : { border: "border-emerald-300", text: "text-emerald-600", bar: "bg-emerald-500" }
}

// The word the line uses for a ticket's age, alongside the number.
function statusWord(secs: number | null): string {
  if (secs === null) return "HELD"
  const m = secs / 60
  return m >= LATE_AT ? "LATE" : m >= AMBER_AT ? "COOKING" : "NEW"
}

/* Ordered -> Fired -> Ready. Fired is the earliest line sent (a coursed table
   fires more than once); Ready only lands once every live line is away. */
function timeline(o: KotOrder) {
  const firedStamps = o.items.filter((i) => i.fired_at).map((i) => parse(i.fired_at!))
  const live = o.items.filter((i) => i.state === "cooking" || i.state === "done")
  const readyStamps = live.filter((i) => i.prepared_at).map((i) => parse(i.prepared_at!))
  const allAway = live.length > 0 && live.every((i) => i.state === "done")
  return {
    ordered: parse(o.creation),
    fired: firedStamps.length ? Math.min(...firedStamps) : null,
    ready: allAway && readyStamps.length ? Math.max(...readyStamps) : null,
  }
}

function progressOf(o: KotOrder) {
  const live = o.items.filter((i) => i.state === "cooking" || i.state === "done")
  return { done: live.filter((i) => i.state === "done").length, total: live.length }
}

/* Where the food goes, in the words the kitchen uses. Takeaway and delivery
   have no table or room, and the pass needs to know to pack them. */
function destination(o: KotOrder): string {
  if (o.order_type === "Takeaway") return "TAKEAWAY"
  if (o.order_type === "Delivery") return "DELIVERY"
  if (o.room_no) return `Room ${o.room_no}`
  if (o.table_no) return `Table ${o.table_no}`
  return o.outlet_name
}

/* Tags for work the ticket implies but never lists: room service needs a tray
   laid up, takeaway needs packing. The chef would otherwise plate it wrong. */
function serviceTags(o: KotOrder): string[] {
  if (o.order_type === "Room Service") return ["TRAY SET-UP"]
  if (o.order_type === "Takeaway" || o.order_type === "Delivery") return ["PACK TO GO"]
  return []
}

function groupBy(items: KotItem[], key: (i: KotItem) => string, order: string[]): [string, KotItem[]][] {
  const seen = [...new Set(items.map(key))]
  const ranked = [...seen].sort((a, b) => {
    const ia = order.indexOf(a), ib = order.indexOf(b)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return ranked.map((k) => [k, items.filter((i) => key(i) === k)] as [string, KotItem[]])
}

// A ticking clock, so the board ages between refetches instead of jumping.
function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(t)
  }, [ms])
  return now
}

/* A ticket landing on a screen nobody is looking at is the whole reason KDS
   chimes exist. Synthesised, so there is no asset to ship or fail to load. */
function chime() {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const ctx = new Ctx()
    const t0 = ctx.currentTime
    for (const [i, hz] of [880, 1320].entries()) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const at = t0 + i * 0.13
      osc.type = "sine"
      osc.frequency.value = hz
      gain.gain.setValueAtTime(0.0001, at)
      gain.gain.exponentialRampToValueAtTime(0.25, at + 0.012)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.12)
      osc.connect(gain).connect(ctx.destination)
      osc.start(at)
      osc.stop(at + 0.13)
    }
    setTimeout(() => void ctx.close(), 600)
  } catch {
    // Browsers block audio until the screen has been touched once. The board
    // still works; the chime starts once someone taps anything.
  }
}

function VegDot({ veg }: { veg: 0 | 1 | null }) {
  if (veg === null) return null
  // The Indian mark: green dot in a green square = veg, maroon triangle in a
  // maroon square = non-veg. Shape carries it, so it survives a colourblind
  // cook and a sun-washed screen.
  return (
    <span
      aria-label={veg ? "Veg" : "Non-veg"}
      className={cn("grid size-4 shrink-0 place-items-center rounded-[3px] border-2",
        veg ? "border-emerald-600" : "border-rose-700")}>
      {veg ? (
        <span className="size-1.5 rounded-full bg-emerald-600" />
      ) : (
        <span className="size-0 border-x-[3px] border-b-[5px] border-x-transparent border-b-rose-700" />
      )}
    </span>
  )
}

/* The allergen alarm. The match is a guard, not a guarantee, so the guest's
   own words always ride along with it. */
function AllergyBadge({ hits }: { hits: string[] }) {
  if (!hits.length) return null
  return (
    <span className="inline-flex items-center gap-1 rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-white">
      <TriangleAlert className="size-3" />{hits.join(" · ")} allergy
    </span>
  )
}

function StationHead({ station, count }: { station: string; count: number }) {
  const Icon = STATION_ICON[station] ?? Utensils
  return (
    <div className="flex items-center gap-2 pt-3">
      <Icon className="size-4 text-zinc-400" />
      <span className="text-xs font-black uppercase tracking-wider text-zinc-500">{station}</span>
      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-bold text-zinc-500">
        {count} item{count === 1 ? "" : "s"}
      </span>
    </div>
  )
}

function Timeline({ order, now }: { order: KotOrder; now: number }) {
  const t = timeline(order)
  const p = progressOf(order)
  const steps: [typeof Inbox, string, number | null][] = [
    [Inbox, "Ordered", t.ordered], [Flame, "Fired", t.fired], [Check, "Ready", t.ready],
  ]
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-zinc-200 bg-zinc-50/70 px-5 py-2.5">
      <div className="flex items-center gap-5">
        {steps.map(([Icon, label, at]) => (
          <div key={label} className="flex items-center gap-1.5">
            <Icon className={cn("size-4", at ? "text-brand-600" : "text-zinc-300")} />
            <span className={cn("text-xs font-bold", at ? "text-zinc-700" : "text-zinc-400")}>{label}</span>
            <span className={cn("text-xs tabular-nums", at ? "text-zinc-600" : "text-zinc-300")}>
              {at ? clockOf(at) : "—"}
            </span>
          </div>
        ))}
      </div>
      {p.total > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold tabular-nums text-zinc-600">{p.done} / {p.total} ready</span>
          <div className="h-1.5 w-28 overflow-hidden rounded-full bg-zinc-200">
            <div className="h-full rounded-full bg-brand-600 transition-all"
              style={{ width: `${Math.round((p.done / p.total) * 100)}%` }} />
          </div>
        </div>
      )}
      <span className="sr-only">{now}</span>
    </div>
  )
}

function Line({ it, order, busy, onAction, big }: {
  it: KotItem; order: KotOrder; busy: string | null
  onAction: (fn: string, params: Record<string, unknown>) => void
  big?: boolean
}) {
  const done = it.state === "done"
  return (
    <li className={cn("flex items-center gap-3", big ? "py-3" : "py-2")}>
      <span className={cn("shrink-0 text-center font-black tabular-nums",
        big ? "w-10 text-2xl" : "w-7 text-lg",
        done ? "rounded-lg bg-zinc-100 text-zinc-400" : "text-brand-700")}>
        {Math.round(it.qty)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <VegDot veg={it.is_veg} />
          <span className={cn("truncate font-bold", big ? "text-lg" : "text-sm",
            done ? "text-zinc-400 line-through" : "text-zinc-900")}>
            {it.item_name}
          </span>
          {!done && <AllergyBadge hits={it.allergy_hits} />}
        </div>
        {it.instructions && (
          <div className={cn("mt-0.5 font-bold", big ? "text-base" : "text-xs",
            done ? "text-zinc-400" : "text-rose-600")}>
            {done ? it.instructions : `! ${it.instructions}`}
          </div>
        )}
      </div>
      {done ? (
        <Button disabled={busy === order.name + it.name}
          onClick={() => onAction("recall_prepared", { item_row: it.name })}
          title="Undo — put it back on the board"
          className={cn("shrink-0", big ? "h-12 px-6 text-base" : "h-9 px-3 text-xs")}>
          <Check className={big ? "size-5" : "size-4"} />Ready
        </Button>
      ) : (
        <Button variant="outline" disabled={busy === order.name + it.name}
          onClick={() => onAction("mark_prepared", { item_row: it.name })}
          className={cn("shrink-0 border-brand-600 text-brand-700",
            big ? "h-12 px-6 text-base" : "h-9 px-3 text-xs")}>
          Mark ready
        </Button>
      )}
    </li>
  )
}

/* The ticket opens as a drawer over the right half, never full screen: the
   board is what the line works from and it stays readable and tappable, so
   tapping another card swaps this panel rather than needing a close first.
   The board reflows into the free half (see the grid below) so no card ends
   up hidden underneath. Targets stay large - gloved, wet, greasy hands. */
function TicketDetail({ order, onClose, onAction, busy, now }: {
  order: KotOrder
  onClose: () => void
  onAction: (fn: string, params: Record<string, unknown>) => void
  busy: string | null
  now: number
}) {
  const secs = firedAgeSecs(order, now)
  const tone = ageTone(secs)
  const live = order.items.filter((i) => i.state === "cooking" || i.state === "done")
  const held = order.items.filter((i) => i.state === "held")
  const cancelled = order.items.filter((i) => i.state === "cancelled")
  const anyDone = live.some((i) => i.state === "done")
  const anyCooking = live.some((i) => i.state === "cooking")

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", esc)
    return () => window.removeEventListener("keydown", esc)
  }, [onClose])

  return (
    <aside
      aria-label={`Ticket ${order.kot_no ?? ""} ${destination(order)}`}
      className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-zinc-200 bg-white shadow-2xl sm:w-1/2">
      <div className={cn("h-1.5 w-full shrink-0", tone.bar)} />
      <header className="flex shrink-0 items-start justify-between gap-4 px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-2xl font-black tabular-nums">
              {order.kot_no ? `KOT ${order.kot_no}` : "KOT —"} · {destination(order)}
            </span>
            {order.order_type && (
              <span className="rounded bg-brand-50 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-brand-700">
                {order.order_type}
              </span>
            )}
          </div>
          <div className="mt-1 text-sm text-zinc-500">
            {[order.captain ? `Captain: ${order.captain.split("@")[0]}` : null,
              order.guests ? `${order.guests} guests` : null,
              order.outlet_name,
              order.order_total ? `Order ₹${Math.round(order.order_total)}` : null]
              .filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <div className="text-right">
            <div className={cn("text-3xl font-black tabular-nums leading-none", tone.text)}>
              {secs === null ? "—" : `${Math.floor(secs / 60)}m`}
            </div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-widest text-zinc-400">elapsed</div>
          </div>
          <button onClick={onClose} aria-label="Back to board"
            className="grid size-12 place-items-center rounded-xl border border-zinc-300 text-zinc-600 hover:bg-zinc-100">
            <X className="size-6" />
          </button>
        </div>
      </header>

      <Timeline order={order} now={now} />

      <div className="flex-1 overflow-y-auto px-5 py-3">
        {order.allergy_note && (
          <div className="mb-3 flex items-start gap-2 rounded-xl border-2 border-rose-500 bg-rose-50 px-4 py-3">
            <TriangleAlert className="mt-0.5 size-5 shrink-0 text-rose-600" />
            <div>
              <div className="text-xs font-black uppercase tracking-wide text-rose-700">Guest allergy</div>
              <p className="text-base font-bold text-rose-900">{order.allergy_note}</p>
            </div>
          </div>
        )}

        {cancelled.map((it) => (
          <div key={it.name} className="mb-3 rounded-xl border-2 border-rose-500 bg-rose-50 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs font-black tracking-wide text-rose-700">CANCELLED — STOP COOKING</div>
                <div className="mt-0.5 truncate text-lg font-bold text-rose-900 line-through">
                  {Math.round(it.qty)}× {it.item_name}
                </div>
                {it.void_reason && <div className="text-sm text-rose-700">{it.void_reason}</div>}
              </div>
              <Button variant="outline" disabled={busy === order.name + it.name}
                onClick={() => onAction("acknowledge_void", { item_row: it.name })}
                className="h-12 shrink-0 border-rose-400 px-5 text-base text-rose-700">
                Got it
              </Button>
            </div>
          </div>
        ))}

        {groupBy(live, (i) => i.prep_station ?? "Kitchen", STATIONS).map(([station, items]) => (
          <div key={station}>
            <StationHead station={station} count={items.length} />
            <ul className="divide-y divide-zinc-100">
              {items.map((it) => (
                <Line key={it.name} it={it} order={order} busy={busy} onAction={onAction} big />
              ))}
            </ul>
          </div>
        ))}

        {order.held_courses.map((course) => {
          const items = held.filter((i) => i.course === course)
          if (!items.length) return null
          return (
            <div key={course} className="mt-4 rounded-xl border-2 border-dashed border-amber-300 bg-amber-50/40 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-amber-700">
                  <Lock className="size-3.5" />{course} · held
                </span>
                <Button disabled={busy === order.name + course}
                  onClick={() => onAction("fire_kot", { course })}
                  className="h-11 bg-amber-600 px-5 text-base hover:bg-amber-700">
                  <Flame className="size-4" />Fire {course.toLowerCase()}
                </Button>
              </div>
              <ul className="space-y-1.5">
                {items.map((it) => (
                  <li key={it.name} className="flex items-center gap-2">
                    <span className="w-6 shrink-0 text-center font-bold tabular-nums text-zinc-500">
                      {Math.round(it.qty)}
                    </span>
                    <VegDot veg={it.is_veg} />
                    <span className="truncate text-base text-zinc-600">{it.item_name}</span>
                    <AllergyBadge hits={it.allergy_hits} />
                  </li>
                ))}
              </ul>
            </div>
          )
        })}

        {order.notes && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <p className="text-sm font-semibold text-amber-900">
              <span className="font-black">Table note: </span>{order.notes}
            </p>
          </div>
        )}
      </div>

      <footer className="flex shrink-0 items-center gap-3 border-t border-zinc-200 p-4">
        {anyDone && (
          <Button variant="outline" disabled={busy === order.name}
            onClick={() => onAction("recall_prepared", {})}
            className="h-16 shrink-0 px-6 text-base">
            <Undo2 className="size-5" />Recall
          </Button>
        )}
        {!order.accepted_at && anyCooking ? (
          <Button disabled={busy === order.name} onClick={() => onAction("accept_ticket", {})}
            className="h-16 flex-1 justify-center bg-amber-600 text-lg font-bold hover:bg-amber-700">
            <Play className="size-6" />Start / accept
          </Button>
        ) : anyCooking ? (
          <Button disabled={busy === order.name} onClick={() => onAction("mark_prepared", {})}
            className="h-16 flex-1 justify-center text-lg font-bold">
            <Check className="size-6" />All ready — send to pass
          </Button>
        ) : null}
      </footer>
    </aside>
  )
}

export default function Kitchen() {
  const [station, setStation] = useState("")
  const [outlet, setOutlet] = useState("")
  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [orders, setOrders] = useState<KotOrder[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [openOrder, setOpenOrder] = useState<string | null>(null)
  const [sound, setSound] = useState(() => localStorage.getItem(CHIME_KEY) !== "off")
  const now = useNow()

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
    // live: re-fetch the moment an order fires or a line is marked ready
    // (socket via subscribeRealtime, with its own polling fallback)
    const unsub = subscribeRealtime(load)
    const t = setInterval(load, 15_000) // safety net
    return () => { unsub(); clearInterval(t) }
  }, [load])

  // Chime only for tickets that arrive after this screen has settled, so a
  // reload or a filter change does not sound like a rush.
  const seen = useRef<Set<string> | null>(null)
  useEffect(() => {
    const ids = new Set(orders.map((o) => o.name))
    if (seen.current === null) { seen.current = ids; return }
    const fresh = [...ids].some((id) => !seen.current!.has(id))
    seen.current = ids
    if (fresh && sound) chime()
  }, [orders, sound])

  const toggleSound = useCallback(() => {
    setSound((on) => {
      localStorage.setItem(CHIME_KEY, on ? "off" : "on")
      if (!on) chime() // confirm it works, and unlock audio on this tap
      return !on
    })
  }, [])

  const act = useCallback(async (order: string, fn: string, params: Record<string, unknown>) => {
    setBusy(order + (params.item_row ?? params.course ?? ""))
    try {
      await call(`kamra.pos.${fn}`, { order, ...params })
      load()
    } finally {
      setBusy(null)
    }
  }, [load])

  // Oldest fired ticket first: the board reads top-left to bottom-right, and
  // the thing closest to being late should be the first thing a cook sees.
  const sorted = useMemo(() => {
    return [...orders].sort((a, b) => {
      const sa = firedAgeSecs(a, now), sb = firedAgeSecs(b, now)
      if (sa === null) return sb === null ? 0 : 1
      if (sb === null) return -1
      return sb - sa
    })
  }, [orders, now])

  // The open ticket is re-read from the live list, so it stays in step with
  // the board; if it clears (all ready, or the captain settles it) we fall
  // back to the board rather than stranding the chef on a dead ticket.
  const open = openOrder ? orders.find((o) => o.name === openOrder) : undefined
  useEffect(() => {
    if (openOrder && orders.length && !open) setOpenOrder(null)
  }, [openOrder, orders, open])

  return (
    // With a ticket open the board lives in the left half, so the drawer
    // covers empty space instead of tickets the line still needs to read.
    <div className={cn("space-y-4 transition-[padding] duration-200",
      open && "sm:pr-[calc(50vw+1rem)]")}>
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
          <div className="flex flex-wrap rounded-lg border border-zinc-200 bg-white p-0.5 text-sm">
            {["", ...STATIONS].map((s) => (
              <button key={s} onClick={() => setStation(s)}
                className={"rounded-md px-3 py-1.5 font-medium " +
                  (station === s ? "bg-brand-600 text-white" : "text-zinc-600")}>
                {s || "All"}
              </button>
            ))}
          </div>
          <button onClick={toggleSound}
            aria-pressed={sound}
            className={cn("inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm font-medium",
              sound ? "border-amber-300 bg-amber-50 text-amber-700" : "border-zinc-300 bg-white text-zinc-400")}>
            {sound ? <Bell className="size-4" /> : <BellOff className="size-4" />}
            Sound {sound ? "on" : "off"}
          </button>
          <button onClick={load} aria-label="Refresh"><RefreshCw className="size-5 text-zinc-400" /></button>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 p-12 text-center text-zinc-400">
          No open tickets. The kitchen is clear.
        </div>
      ) : (
        <div className={cn("grid gap-3",
          open ? "lg:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4")}>
          {sorted.map((o) => {
            const secs = firedAgeSecs(o, now)
            const tone = ageTone(secs)
            const live = o.items.filter((i) => i.state === "cooking" || i.state === "done")
            const held = o.items.filter((i) => i.state === "held")
            const cancelled = o.items.filter((i) => i.state === "cancelled")
            const p = progressOf(o)
            const stations = [...new Set(live.map((i) => i.prep_station).filter(Boolean))]
            const tags = [...stations, ...serviceTags(o)]
            const anyCooking = live.some((i) => i.state === "cooking")
            return (
              <div key={o.name}
                className={cn("flex flex-col overflow-hidden rounded-2xl border-2 bg-white",
                  cancelled.length ? "border-rose-500" : tone.border)}>
                <div className={cn("h-1.5 w-full", tone.bar)} />
                <button onClick={() => setOpenOrder(o.name)}
                  className="w-full px-3 py-2 text-left hover:bg-zinc-50">
                  <div className="flex items-start justify-between gap-2">
                    <span className="min-w-0 text-[10px] font-black uppercase tracking-wider text-zinc-400">
                      {o.kot_no ? `KOT ${o.kot_no} · ` : ""}{o.order_type}
                    </span>
                    <span className={cn("shrink-0 text-[10px] font-black uppercase tracking-wider", tone.text)}>
                      {statusWord(secs)}
                    </span>
                  </div>
                  <div className="flex items-end justify-between gap-2">
                    <span className="min-w-0 truncate text-lg font-bold text-zinc-900">{destination(o)}</span>
                    <span className={cn("inline-flex shrink-0 items-center gap-1 text-lg font-black tabular-nums", tone.text)}>
                      <Clock className="size-4" />{secs === null ? "—" : `${Math.floor(secs / 60)}m`}
                    </span>
                  </div>
                  <div className="truncate text-xs text-zinc-400">
                    {[o.guests ? `${o.guests} guests` : null,
                      o.captain ? `Capt. ${o.captain.split("@")[0]}` : null].filter(Boolean).join(" · ")}
                  </div>
                  {tags.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {tags.map((t) => (
                        <span key={t} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-zinc-500">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </button>

                {o.allergy_note && (
                  <div className="flex items-center gap-1.5 bg-rose-600 px-3 py-1 text-xs font-black uppercase tracking-wide text-white">
                    <TriangleAlert className="size-3.5 shrink-0" />
                    <span className="truncate">{o.allergy_note}</span>
                  </div>
                )}

                {cancelled.length > 0 && (
                  <button onClick={() => setOpenOrder(o.name)}
                    className="flex items-center gap-1.5 bg-rose-50 px-3 py-1.5 text-left text-xs font-black text-rose-700">
                    <TriangleAlert className="size-3.5 shrink-0" />
                    {cancelled.length} CANCELLED — STOP
                  </button>
                )}

                <div className="flex-1 border-t border-zinc-100 px-3">
                  {groupBy(live, (i) => i.course, COURSE_ORDER).map(([course, items]) => (
                    <div key={course}>
                      <div className="pt-2 text-[10px] font-black uppercase tracking-wider text-zinc-400">
                        {course}
                      </div>
                      <ul className="divide-y divide-zinc-50">
                        {items.map((it) => (
                          <Line key={it.name} it={it} order={o} busy={busy}
                            onAction={(fn, params) => act(o.name, fn, params)} />
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>

                {p.total > 0 && (
                  <div className="px-3 py-1 text-right text-[11px] font-bold tabular-nums text-zinc-400">
                    {p.done} of {p.total} ready
                  </div>
                )}

                {o.notes && (
                  <div className="mx-3 mb-1 flex items-start gap-1 rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
                    <TriangleAlert className="mt-px size-3 shrink-0" />{o.notes}
                  </div>
                )}

                {o.held_courses.map((course) => (
                  <div key={course} className="mx-2 mb-2 rounded-lg border border-dashed border-amber-300 bg-amber-50/50 p-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1 truncate text-[10px] font-black uppercase tracking-wider text-amber-700">
                        <Lock className="size-3" />{course} held ·{" "}
                        {held.filter((i) => i.course === course).length}
                      </span>
                      <Button disabled={busy === o.name + course}
                        onClick={() => act(o.name, "fire_kot", { course })}
                        className="h-9 shrink-0 bg-amber-600 px-3 text-xs hover:bg-amber-700">
                        <Flame className="size-3.5" />Fire
                      </Button>
                    </div>
                  </div>
                ))}

                {anyCooking && (
                  <div className="p-2 pt-0">
                    {!o.accepted_at ? (
                      <Button variant="outline" disabled={busy === o.name}
                        onClick={() => act(o.name, "accept_ticket", {})}
                        className="h-11 w-full justify-center border-amber-400 text-amber-700 hover:bg-amber-50">
                        <Flame className="size-4" />Start / accept
                      </Button>
                    ) : (
                      <Button className="h-11 w-full justify-center" disabled={busy === o.name}
                        onClick={() => act(o.name, "mark_prepared", {})}>
                        <Check className="size-4" />All ready
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {open && (
        <TicketDetail order={open} busy={busy} now={now}
          onClose={() => setOpenOrder(null)}
          onAction={(fn, params) => act(open.name, fn, params)} />
      )}
    </div>
  )
}
