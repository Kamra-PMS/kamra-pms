import { useCallback, useEffect, useMemo, useState } from "react"
import { Shirt, Zap, Plus, Minus, X, Printer, Clock } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { laundryDocketHtml, printThermal } from "../lib/thermal"
import { listResource, serverError } from "../lib/resource"
import { useAuth } from "../lib/auth"
import { Sheet } from "../components/ui/sheet"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cn } from "../lib/utils"
import { cur } from "../lib/money"
import { useT } from "../lib/i18n"
import {
  ExpressToggle,
  inr,
  LAUNDRY_SERVICES,
  laundryApi,
  STATUS_TONE,
  useLaundryBoard,
  type LaundryOrder,
  type OrderType,
  type Rate,
  type Room,
} from "./laundry/shared"

/** Desktop home for the full laundry module: the operational board (pickup →
 * collect → process → deliver + cancel), the price menu (rate card) and a
 * billing view. Reuses kamra.laundry.* — the same backend the /hk phone app
 * drives — so the two stay in lockstep. */

const OPERATOR_ROLES = [
  "Housekeeping",
  "Front Desk",
  "Hotel Admin",
  "System Manager",
  "Administrator",
]
const RATE_EDIT_ROLES = [
  "Front Desk",
  "Finance",
  "Hotel Admin",
  "System Manager",
  "Administrator",
]

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Tab = "board" | "menu" | "billing"

export default function Laundry() {
  const { t } = useT()
  const { roles } = useAuth()
  const property = getCurrentProperty()
  const canOperate = roles.some((r) => OPERATOR_ROLES.includes(r))
  const canEditRates = roles.some((r) => RATE_EDIT_ROLES.includes(r))

  const { board, rates, error, busy, act, reload } = useLaundryBoard(property)
  const [rooms, setRooms] = useState<Room[]>([])
  const [tab, setTab] = useState<Tab>("board")

  useEffect(() => {
    listResource("Room", {
      fields: ["name", "room_number", "occupancy_status"],
      filters: [["property", "=", property]],
      orderBy: "room_number asc",
    })
      .then((r) => setRooms(r as unknown as Room[]))
      .catch(() => {})
  }, [property])

  const occupied = useMemo(
    () => rooms.filter((r) => r.occupancy_status === "Occupied"),
    [rooms],
  )

  // dialog state (desktop right-drawer surfaces)
  const [pickup, setPickup] = useState<{
    room: string
    notes: string
    express: boolean
    orderType: OrderType
    houseLabel: string
  } | null>(null)
  const [counting, setCounting] = useState<{
    order: string | null
    room: string
    express: boolean
    qty: Record<string, number>
    orderType: OrderType
    houseLabel: string
    comp: boolean
  } | null>(null)
  const [returning, setReturning] = useState<{
    order: LaundryOrder
    back: Record<string, number>
    note: string
  } | null>(null)
  const [cancelling, setCancelling] = useState<{
    order: LaundryOrder
    reason: string
  } | null>(null)

  const countTotal = counting
    ? rates.reduce(
        (s, r) =>
          s +
          (counting.qty[r.name] || 0) *
            (counting.express ? r.express_rate : r.rate),
        0,
      )
    : 0
  const countPieces = counting
    ? Object.values(counting.qty).reduce((s, q) => s + q, 0)
    : 0
  const returnPending = returning
    ? returning.order.items.reduce(
        (s, it) => s + it.qty - (returning.back[it.name] ?? it.returned_qty),
        0,
      )
    : 0

  async function submitCollect() {
    if (!counting || countPieces === 0) return
    const items = rates
      .filter((r) => (counting.qty[r.name] || 0) > 0)
      .map((r) => ({
        item_name: r.item_name,
        service_type: r.service_type,
        qty: counting.qty[r.name],
      }))
    await act(async () => {
      await laundryApi.collect(
        property,
        counting.room,
        items,
        counting.order,
        counting.express,
        counting.orderType,
        counting.houseLabel || null,
        counting.comp,
      )
      setCounting(null)
    })
  }

  async function submitDeliver() {
    if (!returning) return
    const r = returning
    await act(async () => {
      await laundryApi.returnItems(
        r.order.name,
        Object.fromEntries(
          r.order.items.map((it) => [
            it.name,
            r.back[it.name] ?? it.returned_qty,
          ]),
        ),
      )
      await laundryApi.deliver(
        r.order.name,
        returnPending > 0 ? r.note : null,
      )
      setReturning(null)
    })
  }

  async function submitCancel() {
    if (!cancelling || !cancelling.reason.trim()) return
    const c = cancelling
    await act(async () => {
      await laundryApi.cancel(c.order.name, c.reason.trim())
      setCancelling(null)
    })
  }

  const open = board?.open ?? []
  const requested = open.filter((o) => o.status === "Requested")
  const inHand = open.filter((o) => o.status !== "Requested")
  const recent = board?.recent ?? []

  const OrderCard = ({ o }: { o: LaundryOrder }) => (
    <li className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold tabular-nums">{o.room_no}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{o.guest_name || o.name}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={STATUS_TONE[o.status] || "zinc"}>{t(o.status)}</Badge>
            {o.order_type === "House" && <Badge tone="indigo">{t("house")}</Badge>}
            {!!o.complimentary && o.order_type !== "House" && (
              <Badge tone="green">{t("comp")}</Badge>
            )}
            {!!o.express && (
              <Badge tone="amber">
                <Zap className="mr-0.5 size-3" />
                {t("express")}
              </Badge>
            )}
            {o.pieces > 0 && <Badge tone="zinc">{t("{n} pc", { n: o.pieces })}</Badge>}
            {o.pending > 0 && o.status !== "Requested" && (
              <Badge tone="rose">{t("{n} pending", { n: o.pending })}</Badge>
            )}
            {o.overdue && <Badge tone="rose">{t("overdue")}</Badge>}
          </div>
        </div>
        {o.total > 0 && (
          <span className="text-sm font-semibold tabular-nums">
            {cur()}{inr(o.total)}
          </span>
        )}
      </div>
      {o.ready_by && !["Delivered", "Cancelled"].includes(o.status) && (
        <p
          className={cn(
            "mt-1 flex items-center gap-1 text-xs",
            o.overdue ? "text-rose-600" : "text-zinc-400",
          )}
        >
          <Clock className="size-3" aria-hidden />
          {t("Ready by")} {o.ready_by.slice(0, 16).replace("T", " ")}
        </p>
      )}
      {o.notes && <p className="mt-2 text-sm text-zinc-500">{o.notes}</p>}
      {o.shortage_note && (
        <p className="mt-2 rounded-lg bg-rose-50 px-2.5 py-1.5 text-sm text-rose-700">
          {t("Shortage")}: {o.shortage_note}
        </p>
      )}
      {canOperate && (
        <div className="mt-3 flex flex-wrap gap-2">
          {o.status === "Requested" && (
            <Button
              disabled={busy}
              onClick={() =>
                setCounting({
                  order: o.name,
                  room: o.room,
                  express: !!o.express,
                  qty: {},
                  orderType: (o.order_type as OrderType) || "Guest",
                  houseLabel: o.house_label || "",
                  comp: !!o.complimentary,
                })
              }
            >
              {t("Collect & count")}
            </Button>
          )}
          {o.status === "Collected" && (
            <Button
              disabled={busy}
              onClick={() =>
                act(() => laundryApi.setStatus(o.name, "In Process"))
              }
            >
              {t("Send to laundry")}
            </Button>
          )}
          {o.status === "In Process" && (
            <Button
              disabled={busy}
              onClick={() => act(() => laundryApi.setStatus(o.name, "Ready"))}
            >
              {t("Mark ready")}
            </Button>
          )}
          {["Collected", "In Process", "Ready"].includes(o.status) && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setReturning({ order: o, back: {}, note: "" })}
            >
              {t("Return & deliver")}
            </Button>
          )}
          {o.status !== "Delivered" && o.status !== "Cancelled" && (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setCancelling({ order: o, reason: "" })}
            >
              {t("Cancel")}
            </Button>
          )}
          {o.items?.length > 0 && (
            <Button
              variant="ghost"
              onClick={() =>
                printThermal(
                  `Laundry ${o.name}`,
                  laundryDocketHtml({
                    order: o.name,
                    room_no: o.room_no,
                    guest_name: o.guest_name,
                    order_type: o.order_type,
                    express: !!o.express,
                    ready_by: o.ready_by,
                    items: o.items.map((it) => ({
                      item_name: it.item_name,
                      service_type: it.service_type,
                      qty: it.qty,
                    })),
                    total: o.total,
                  }),
                )
              }
            >
              <Printer className="mr-1 size-4" />
              {t("Docket")}
            </Button>
          )}
        </div>
      )}
    </li>
  )

  const Column = ({
    title,
    orders,
    empty,
  }: {
    title: string
    orders: LaundryOrder[]
    empty: string
  }) => (
    <div className="flex min-w-0 flex-col gap-3">
      <p className="px-1 text-sm font-medium text-zinc-500">
        {title} ({orders.length})
      </p>
      <ul className="space-y-3">
        {orders.map((o) => (
          <OrderCard key={o.name} o={o} />
        ))}
        {orders.length === 0 && (
          <li className="rounded-2xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-400">
            {empty}
          </li>
        )}
      </ul>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Shirt className="size-5 text-brand-600" />
            {t("Laundry")}
          </h1>
          <p className="text-sm text-zinc-400">
            {t("Guest laundry — pickup, processing, return and billing.")}
          </p>
        </div>
        {tab === "board" && canOperate && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() =>
                setPickup({
                  room: "",
                  notes: "",
                  express: false,
                  orderType: "Guest",
                  houseLabel: "",
                })
              }
            >
              {t("Log pickup request")}
            </Button>
            <Button
              onClick={() =>
                setCounting({
                  order: null,
                  room: "",
                  express: false,
                  qty: {},
                  orderType: "Guest",
                  houseLabel: "",
                  comp: false,
                })
              }
            >
              <Shirt className="mr-1 size-4" />
              {t("Collect now")}
            </Button>
          </div>
        )}
      </div>

      <div className="flex gap-1 rounded-xl bg-zinc-100 p-1 text-sm font-medium">
        {(
          [
            ["board", t("Board")],
            ["menu", t("Price menu")],
            ["billing", t("Billing")],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            className={cn(
              "flex-1 rounded-lg px-3 py-1.5 transition",
              tab === id
                ? "bg-white text-zinc-900 shadow-sm"
                : "text-zinc-500 hover:text-zinc-700",
            )}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}

      {tab === "board" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Column
            title={t("Pickup requests")}
            orders={requested}
            empty={t("No pickups waiting.")}
          />
          <Column
            title={t("In hand")}
            orders={inHand}
            empty={t("No laundry out right now.")}
          />
          <Column title={t("Recent")} orders={recent} empty={t("Nothing recent.")} />
        </div>
      )}

      {tab === "menu" && (
        <PriceMenu
          rates={rates}
          property={property}
          canEdit={canEditRates}
          onChanged={reload}
        />
      )}

      {tab === "billing" && <Billing recent={recent} property={property} />}

      {/* pickup request drawer */}
      {pickup && (
        <Sheet
          title={t("Laundry pickup request")}
          onClose={() => setPickup(null)}
          footer={
            <Button
              className="w-full"
              disabled={
                busy ||
                (pickup.orderType === "Guest"
                  ? !pickup.room
                  : !pickup.houseLabel.trim())
              }
              onClick={() =>
                act(async () => {
                  await laundryApi.requestPickup(
                    property,
                    pickup.room,
                    pickup.notes || null,
                    pickup.express,
                    pickup.orderType,
                    pickup.houseLabel || null,
                  )
                  setPickup(null)
                })
              }
            >
              {t("Add to pickup queue")}
            </Button>
          }
        >
          <div className="space-y-3">
            <OrderTypeToggle
              value={pickup.orderType}
              onChange={(t) => setPickup({ ...pickup, orderType: t })}
            />
            {pickup.orderType === "Guest" ? (
              <RoomSelect
                value={pickup.room}
                rooms={occupied}
                onChange={(room) => setPickup({ ...pickup, room })}
              />
            ) : (
              <input
                className={inputCls}
                placeholder={t("What is it? (Staff uniforms, Pool towels…)")}
                value={pickup.houseLabel}
                onChange={(e) =>
                  setPickup({ ...pickup, houseLabel: e.target.value })
                }
              />
            )}
            <input
              className={inputCls}
              placeholder={t("Notes (bag on door, after 3pm…)")}
              value={pickup.notes}
              onChange={(e) => setPickup({ ...pickup, notes: e.target.value })}
            />
            <ExpressToggle
              value={pickup.express}
              onChange={(v) => setPickup({ ...pickup, express: v })}
            />
          </div>
        </Sheet>
      )}

      {/* count-the-bag drawer */}
      {counting && (
        <Sheet
          title={t("Count the bag")}
          onClose={() => setCounting(null)}
          footer={
            <Button
              className="w-full"
              disabled={
                busy ||
                countPieces === 0 ||
                (!counting.order &&
                  (counting.orderType === "Guest"
                    ? !counting.room
                    : !counting.houseLabel.trim()))
              }
              onClick={submitCollect}
            >
              {t("Collect {n} piece{s} · {total}", {
                n: countPieces,
                s: countPieces === 1 ? "" : "s",
                total: `${cur()}${inr(countTotal)}`,
              })}
            </Button>
          }
        >
          <div className="space-y-3">
            {!counting.order && (
              <>
                <OrderTypeToggle
                  value={counting.orderType}
                  onChange={(t) =>
                    setCounting({ ...counting, orderType: t, comp: false })
                  }
                />
                {counting.orderType === "Guest" ? (
                  <>
                    <RoomSelect
                      value={counting.room}
                      rooms={occupied}
                      onChange={(room) => setCounting({ ...counting, room })}
                    />
                    <label className="flex items-center gap-2 text-sm text-zinc-600">
                      <input
                        type="checkbox"
                        checked={counting.comp}
                        onChange={(e) =>
                          setCounting({ ...counting, comp: e.target.checked })
                        }
                      />
                      {t("Complimentary — don't bill the guest")}
                    </label>
                  </>
                ) : (
                  <input
                    className={inputCls}
                    placeholder={t("What is it? (Staff uniforms, Pool towels…)")}
                    value={counting.houseLabel}
                    onChange={(e) =>
                      setCounting({ ...counting, houseLabel: e.target.value })
                    }
                  />
                )}
              </>
            )}
            <ExpressToggle
              value={counting.express}
              onChange={(v) => setCounting({ ...counting, express: v })}
            />
            <div className="space-y-1">
              {rates.map((r) => {
                const q = counting.qty[r.name] || 0
                const price = counting.express ? r.express_rate : r.rate
                return (
                  <div
                    key={r.name}
                    className={cn(
                      "flex items-center gap-2 rounded-xl border px-3 py-2",
                      q > 0
                        ? "border-brand-300 bg-brand-50"
                        : "border-zinc-200",
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {r.item_name}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {r.service_type} · {cur()}{inr(price)}
                      </p>
                    </div>
                    <Stepper
                      value={q}
                      onDec={() =>
                        setCounting({
                          ...counting,
                          qty: {
                            ...counting.qty,
                            [r.name]: Math.max(0, q - 1),
                          },
                        })
                      }
                      onInc={() =>
                        setCounting({
                          ...counting,
                          qty: { ...counting.qty, [r.name]: q + 1 },
                        })
                      }
                    />
                  </div>
                )
              })}
              {rates.length === 0 && (
                <p className="py-4 text-center text-sm text-zinc-400">
                  {t("No rate card yet — add laundry rates in the Price menu tab.")}
                </p>
              )}
            </div>
          </div>
        </Sheet>
      )}

      {/* return & deliver drawer */}
      {returning && (
        <Sheet
          title={t("Return to room {room}", { room: returning.order.room_no })}
          onClose={() => setReturning(null)}
          footer={
            <Button
              className="w-full"
              disabled={busy || (returnPending > 0 && !returning.note.trim())}
              onClick={submitDeliver}
            >
              {t("Deliver & bill {total}{short}", {
                total: `${cur()}${inr(returning.order.total)}`,
                short: returnPending > 0 ? t(" ({n} short)", { n: returnPending }) : "",
              })}
            </Button>
          }
        >
          <div className="space-y-3">
            <button
              type="button"
              className="w-full rounded-xl border border-emerald-300 bg-emerald-50 py-2.5 text-sm font-semibold text-emerald-700"
              onClick={() =>
                setReturning({
                  ...returning,
                  back: Object.fromEntries(
                    returning.order.items.map((it) => [it.name, it.qty]),
                  ),
                })
              }
            >
              {t("Everything came back")}
            </button>
            <div className="space-y-1">
              {returning.order.items.map((it) => {
                const back = returning.back[it.name] ?? it.returned_qty
                return (
                  <div
                    key={it.name}
                    className="flex items-center gap-2 rounded-xl border border-zinc-200 px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {it.item_name}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {it.service_type} · {t("collected {n}", { n: it.qty })}
                      </p>
                    </div>
                    <Stepper
                      count={`${back}/${it.qty}`}
                      tone={back < it.qty ? "short" : "ok"}
                      onDec={() =>
                        setReturning({
                          ...returning,
                          back: {
                            ...returning.back,
                            [it.name]: Math.max(0, back - 1),
                          },
                        })
                      }
                      onInc={() =>
                        setReturning({
                          ...returning,
                          back: {
                            ...returning.back,
                            [it.name]: Math.min(it.qty, back + 1),
                          },
                        })
                      }
                    />
                  </div>
                )
              })}
            </div>
            {returnPending > 0 && (
              <input
                className="w-full rounded-xl border border-rose-300 bg-rose-50 px-3 py-2.5 text-sm"
                placeholder={t("{n} piece(s) short — why? (required)", { n: returnPending })}
                value={returning.note}
                onChange={(e) =>
                  setReturning({ ...returning, note: e.target.value })
                }
              />
            )}
          </div>
        </Sheet>
      )}

      {/* cancel drawer */}
      {cancelling && (
        <Sheet
          title={t("Cancel laundry — room {room}", { room: cancelling.order.room_no })}
          onClose={() => setCancelling(null)}
          footer={
            <Button
              className="w-full"
              variant="outline"
              disabled={busy || !cancelling.reason.trim()}
              onClick={submitCancel}
            >
              {t("Cancel this order")}
            </Button>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-zinc-500">
              {t("This closes the bag without billing. Tell us why — it's recorded on the order.")}
            </p>
            <input
              className={inputCls}
              autoFocus
              placeholder={t("Reason (guest declined, duplicate…)")}
              value={cancelling.reason}
              onChange={(e) =>
                setCancelling({ ...cancelling, reason: e.target.value })
              }
            />
          </div>
        </Sheet>
      )}
    </div>
  )
}

function OrderTypeToggle({
  value,
  onChange,
}: {
  value: OrderType
  onChange: (t: OrderType) => void
}) {
  const { t } = useT()
  return (
    <div className="flex gap-1 rounded-lg bg-zinc-100 p-1 text-sm font-medium">
      {(["Guest", "House"] as OrderType[]).map((ot) => (
        <button
          key={ot}
          type="button"
          className={cn(
            "flex-1 rounded-md px-3 py-1.5",
            value === ot
              ? "bg-white text-zinc-900 shadow-sm"
              : "text-zinc-500",
          )}
          onClick={() => onChange(ot)}
        >
          {ot === "Guest" ? t("Guest") : t("House (uniforms / linen)")}
        </button>
      ))}
    </div>
  )
}

function RoomSelect({
  value,
  rooms,
  onChange,
}: {
  value: string
  rooms: Room[]
  onChange: (room: string) => void
}) {
  const { t } = useT()
  return (
    <select
      className={inputCls}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{t("Room…")}</option>
      {rooms.map((r) => (
        <option key={r.name} value={r.name}>
          {t("Room {n}", { n: r.room_number })}
        </option>
      ))}
    </select>
  )
}

function Stepper({
  value,
  count,
  tone,
  onInc,
  onDec,
}: {
  value?: number
  count?: string
  tone?: "ok" | "short"
  onInc: () => void
  onDec: () => void
}) {
  const { t } = useT()
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="rounded-lg border border-zinc-300 p-1.5"
        aria-label={t("less")}
        onClick={onDec}
      >
        <Minus className="size-4" />
      </button>
      <span
        className={cn(
          "text-center text-base font-bold tabular-nums",
          count ? "w-10" : "w-6",
          tone === "short"
            ? "text-rose-600"
            : tone === "ok"
              ? "text-emerald-700"
              : "",
        )}
      >
        {count ?? value}
      </span>
      <button
        type="button"
        className="rounded-lg border border-zinc-300 p-1.5"
        aria-label={t("more")}
        onClick={onInc}
      >
        <Plus className="size-4" />
      </button>
    </div>
  )
}

/** The price menu (rate card) — read-only for viewers, editable for
 * Front Desk / Finance. Adapted from Settings' LaundryRatesCard. */
function PriceMenu({
  rates,
  property,
  canEdit,
  onChanged,
}: {
  rates: Rate[]
  property: string
  canEdit: boolean
  onChanged: () => void
}) {
  const { t } = useT()
  const [form, setForm] = useState<{
    name?: string
    item: string
    service: string
    rate: string
    express: string
  } | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const save = useCallback(async () => {
    if (!form) return
    setErr(null)
    try {
      await call("kamra.laundry.save_laundry_rate", {
        property,
        name: form.name || null,
        item_name: form.item,
        service_type: form.service,
        rate: form.rate,
        express_rate: form.express || null,
      })
      setForm(null)
      onChanged()
    } catch (e) {
      setErr(serverError(e))
    }
  }, [form, property, onChanged])

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t("Laundry rate card")}</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            {t("Per-item prices the app quotes and bills from. Blank express = 1.5× the normal rate.")}
          </p>
        </div>
        {canEdit && (
          <Button
            variant="outline"
            onClick={() =>
              setForm({ item: "", service: "Wash & Iron", rate: "", express: "" })
            }
          >
            {t("Add rate")}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {err && (
          <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {err}
          </p>
        )}
        {form && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-zinc-50 p-2">
            <input
              className="w-36 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              placeholder={t("Item (Shirt…)")}
              value={form.item}
              onChange={(e) => setForm({ ...form, item: e.target.value })}
              autoFocus
            />
            <select
              className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              value={form.service}
              onChange={(e) => setForm({ ...form, service: e.target.value })}
            >
              {LAUNDRY_SERVICES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <input
              className="w-24 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              placeholder={t("Rate {cur}", { cur: cur() })}
              inputMode="numeric"
              value={form.rate}
              onChange={(e) =>
                setForm({ ...form, rate: e.target.value.replace(/[^\d.]/g, "") })
              }
            />
            <input
              className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              placeholder={t("Express {cur} (opt)", { cur: cur() })}
              inputMode="numeric"
              value={form.express}
              onChange={(e) =>
                setForm({
                  ...form,
                  express: e.target.value.replace(/[^\d.]/g, ""),
                })
              }
            />
            <Button disabled={!form.item.trim() || !form.rate} onClick={save}>
              {t("Save")}
            </Button>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("Cancel")}
            </Button>
          </div>
        )}
        {rates.length === 0 ? (
          <p className="py-3 text-sm text-zinc-400">
            {t("No rates yet{hint}", {
              hint: canEdit ? t(" — add the first item.") : ".",
            })}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-400">
                <th className="py-1.5">{t("Item")}</th>
                <th>{t("Service")}</th>
                <th className="text-right">{t("Rate")}</th>
                <th className="text-right">{t("Express")}</th>
                {canEdit && <th />}
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.name} className="border-t border-zinc-100">
                  <td className="py-1.5 font-medium">{r.item_name}</td>
                  <td className="text-zinc-500">{r.service_type}</td>
                  <td className="text-right tabular-nums">{cur()}{inr(r.rate)}</td>
                  <td className="text-right tabular-nums text-zinc-500">
                    {cur()}{inr(r.express_rate)}
                  </td>
                  {canEdit && (
                    <td className="text-right">
                      <button
                        className="text-xs font-medium text-brand-700 hover:underline"
                        onClick={() =>
                          setForm({
                            name: r.name,
                            item: r.item_name,
                            service: r.service_type,
                            rate: String(r.rate),
                            express: "",
                          })
                        }
                      >
                        {t("Edit")}
                      </button>
                      <button
                        className="ml-2 text-xs text-zinc-400 hover:text-rose-600"
                        onClick={async () => {
                          await call("kamra.laundry.delete_laundry_rate", {
                            name: r.name,
                          })
                          onChanged()
                        }}
                      >
                        {t("Delete")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

interface Revenue {
  days: number
  orders: number
  billed_orders: number
  pieces: number
  revenue: number
  express_orders: number
  non_billable_orders: number
  by_service: { service_type: string; pieces: number; revenue: number }[]
}

/** Billing view — a revenue rollup plus the recent orders and whether each
 * charge posted to the folio. */
function Billing({
  recent,
  property,
}: {
  recent: LaundryOrder[]
  property: string
}) {
  const { t } = useT()
  const delivered = recent.filter((o) => o.status === "Delivered")
  const daySum = delivered.reduce((s, o) => s + (o.total || 0), 0)
  const [rev, setRev] = useState<Revenue | null>(null)

  useEffect(() => {
    call<Revenue>("kamra.laundry.laundry_revenue", { property, days: 30 })
      .then(setRev)
      .catch(() => setRev(null))
  }, [property])

  return (
    <div className="space-y-4">
      {rev && (
        <Card>
          <CardHeader>
            <CardTitle>{t("Last {days} days", { days: rev.days })}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label={t("Revenue")} value={`${cur()}${inr(rev.revenue)}`} />
              <Stat label={t("Billed orders")} value={rev.billed_orders} />
              <Stat label={t("Pieces")} value={rev.pieces} />
              <Stat label={t("Express")} value={rev.express_orders} />
            </div>
            {rev.non_billable_orders > 0 && (
              <p className="mt-2 text-xs text-zinc-400">
                {t("+{n} house / complimentary order{s} (not billed)", {
                  n: rev.non_billable_orders,
                  s: rev.non_billable_orders === 1 ? "" : "s",
                })}
              </p>
            )}
            {rev.by_service.length > 0 && (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-zinc-400">
                    <th className="py-1.5">{t("Service")}</th>
                    <th className="text-right">{t("Pieces")}</th>
                    <th className="text-right">{t("Revenue")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rev.by_service.map((s) => (
                    <tr
                      key={s.service_type}
                      className="border-t border-zinc-100"
                    >
                      <td className="py-1.5">{s.service_type}</td>
                      <td className="text-right tabular-nums">{s.pieces}</td>
                      <td className="text-right tabular-nums">
                        {cur()}{inr(s.revenue)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}
      <Card>
      <CardHeader>
        <CardTitle>{t("Recent laundry billing")}</CardTitle>
      </CardHeader>
      <CardContent>
        {recent.length === 0 ? (
          <p className="py-3 text-sm text-zinc-400">{t("Nothing delivered yet.")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-400">
                <th className="py-1.5">{t("Room")}</th>
                <th>{t("Guest")}</th>
                <th className="text-right">{t("Pieces")}</th>
                <th className="text-right">{t("Total")}</th>
                <th>{t("Status")}</th>
                <th>{t("Folio")}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((o) => (
                <tr key={o.name} className="border-t border-zinc-100">
                  <td className="py-1.5 font-medium tabular-nums">
                    {o.room_no}
                    {o.shortage_note && (
                      <span
                        className="ml-1 text-rose-500"
                        title={o.shortage_note}
                      >
                        !
                      </span>
                    )}
                  </td>
                  <td className="text-zinc-500">{o.guest_name || o.name}</td>
                  <td className="text-right tabular-nums">{o.pieces}</td>
                  <td className="text-right tabular-nums">
                    {o.total > 0 ? `${cur()}${inr(o.total)}` : "—"}
                  </td>
                  <td>
                    <Badge tone={STATUS_TONE[o.status] || "zinc"}>
                      {t(o.status)}
                    </Badge>
                  </td>
                  <td>
                    {o.status !== "Delivered" ? (
                      <span className="text-xs text-zinc-400">—</span>
                    ) : o.posted_to_folio ? (
                      <span className="text-xs font-medium text-emerald-700">
                        {t("Posted")}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-amber-700">
                        <X className="size-3" />
                        {t("not posted")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {delivered.length > 0 && (
          <p className="mt-3 text-right text-sm font-semibold">
            {t("Delivered today")}: {cur()}{inr(daySum)}
          </p>
        )}
      </CardContent>
    </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3">
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}
