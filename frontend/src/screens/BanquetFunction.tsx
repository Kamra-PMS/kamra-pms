/*  One function, end to end.

    The sheet a banquet manager lives in: who and when, what they're
    buying, what it costs after the haggling, what's still open, what's
    been paid, and the paper that comes out the other end.

    Every line carries a chargeable flag. Turn it off and the item stays
    on the event order and the pack list - somebody still has to carry the
    podium - but it drops off the quote and out of the tax. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeft,
  BadgeIndianRupee,
  CalendarClock,
  FileText,
  Gift,
  Handshake,
  Plus,
  Printer,
  Receipt,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react"

import {
  banquet,
  type BanquetCatalogue,
  type FunctionItem,
  type FunctionSheet,
  type FunctionStatus,
  type OpenItem,
  type PaymentTerm,
  type ReceiptDocument,
} from "../lib/api"
import { listResource, serverError, type Row } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import { taxLabel } from "../lib/money"
import {
  daysAway,
  Empty,
  ErrorNote,
  EVENT_TYPES,
  Field,
  inputCls,
  inr,
  ITEM_TYPES,
  NEXT,
  PAY_MODES,
  Select,
  SESSIONS,
  SETUP_STYLES,
  SOURCES,
  StatusPill,
  UOMS,
} from "./banquet/shared"
import { Steps, stepsFor, type StepId } from "./banquet/Steps"
import Economics from "./banquet/Economics"
import MenuComposer from "./banquet/MenuComposer"



export default function BanquetFunction() {
  const { name = "" } = useParams()
  const navigate = useNavigate()
  const [fn, setFn] = useState<FunctionSheet | null>(null)
  const [cat, setCat] = useState<BanquetCatalogue | null>(null)
  const [step, setStep] = useState<StepId>("enquiry")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    banquet
      .sheet(name)
      .then(setFn)
      .catch((e) => setError(serverError(e)))
  }, [name])
  useEffect(load, [load])
  useEffect(() => {
    banquet.catalogue().then(setCat).catch(() => {})
  }, [])

  const act = useCallback(
    async (work: () => Promise<unknown>) => {
      setBusy(true)
      setError(null)
      try {
        await work()
        load()
      } catch (e) {
        setError(serverError(e))
      } finally {
        setBusy(false)
      }
    },
    [load],
  )

  if (!fn) return <Empty>{error ?? "Loading…"}</Empty>

  const away = daysAway(fn.event_date)
  const steps = stepsFor(fn)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <nav aria-label="Breadcrumb" className="mb-1">
            <ol className="flex items-center gap-1.5 text-xs text-zinc-400">
              <li>
                <button
                  onClick={() => navigate("/banquet")}
                  className="inline-flex items-center gap-1 hover:text-zinc-700"
                >
                  <ArrowLeft className="size-3.5" />
                  Banquets
                </button>
              </li>
              <li aria-hidden>/</li>
              <li className="font-mono">{fn.name}</li>
              <li aria-hidden>/</li>
              <li className="text-zinc-600">
                {steps.find((x) => x.id === step)?.label}
              </li>
            </ol>
          </nav>
          <h1 className="flex flex-wrap items-center gap-2 text-lg font-semibold">
            {fn.customer_name}
            <StatusPill status={fn.status} />
            <span className="font-mono text-xs font-normal text-zinc-400">
              {fn.name}
            </span>
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            {fn.event_type}
            {fn.event_name ? ` · ${fn.event_name}` : ""} · {fn.venue} ·{" "}
            {fn.event_date}
            {fn.end_date && fn.end_date !== fn.event_date
              ? ` → ${fn.end_date}`
              : ""}
            {fn.start_time
              ? ` · ${fn.start_time.slice(0, 5)}–${(fn.end_time ?? "").slice(0, 5)}`
              : ""}
            {away >= 0 && fn.status !== "Completed" && (
              <span className="text-zinc-400">
                {" "}
                · in {away} day{away === 1 ? "" : "s"}
              </span>
            )}
          </p>
        </div>
        <StatusActions fn={fn} busy={busy} act={act} />
      </div>

      <ErrorNote error={error} />

      {fn.next_actions.length > 0 && (
        <ul className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          {fn.next_actions.map((a, i) => (
            <li
              key={i}
              className={
                "text-sm " +
                (a.urgency === "high" ? "text-amber-900" : "text-amber-700")
              }
            >
              {a.message}
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Money label="Quote" value={fn.grand_total} sub={`v${fn.quote_version || 0}`} />
        <Money
          label="Received"
          value={fn.advance_received}
          sub={`${fn.receipts.length} receipt${fn.receipts.length === 1 ? "" : "s"}`}
        />
        <Money
          label="Balance"
          value={fn.balance_due}
          tone={fn.balance_due > 0 ? "text-rose-700" : "text-emerald-700"}
        />
        {/* Claiming 100% because nothing has been costed is the most
            flattering possible lie - say "not costed yet" instead. */}
        <Money
          label="Margin"
          value={fn.total_cost ? fn.gross_margin : null}
          sub={
            fn.total_cost
              ? `${fn.margin_percent}% after ${inr(fn.net_cost)} cost`
              : "nothing costed yet — see Cost & margin"
          }
          tone={
            !fn.total_cost
              ? "text-zinc-300"
              : fn.margin_percent >= 35
                ? "text-emerald-700"
                : "text-amber-700"
          }
        />
      </div>

      <Steps steps={steps} current={step} onPick={setStep} />

      {step === "enquiry" && <DetailTab fn={fn} busy={busy} act={act} />}
      {step === "quote" && <ItemsTab fn={fn} cat={cat} busy={busy} act={act} />}
      {step === "margin" && <Economics fn={fn} busy={busy} act={act} />}
      {step === "money" && <MoneyTab fn={fn} busy={busy} act={act} />}
      {step === "documents" && <PaperTab fn={fn} busy={busy} act={act} />}
      {step === "close" && (
        <CloseOutCard fn={fn} busy={busy} act={act} onCount={() => setStep("margin")} />
      )}
    </div>
  )
}

type Act = (work: () => Promise<unknown>) => Promise<void>

function Money({
  label,
  value,
  sub,
  tone = "",
}: {
  label: string
  /** null when the number isn't known yet - shown as a dash, never as a
   *  confident zero or a flattering percentage. */
  value: number | null
  sub?: string
  tone?: string
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
        {label}
      </p>
      <p className={"mt-1 text-xl font-semibold tabular-nums " + tone}>
        {value === null ? "—" : inr(value)}
      </p>
      {sub && <p className="mt-0.5 text-xs text-zinc-400">{sub}</p>}
    </div>
  )
}

/* ── moving the function along ────────────────────────────────────────── */

function StatusActions({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  const [ask, setAsk] = useState<FunctionStatus | null>(null)
  const [reason, setReason] = useState("")
  const options = NEXT[fn.status]

  return (
    <div className="flex flex-wrap items-center gap-2">
      {options.map((s) => (
        <Button
          key={s}
          variant={s === "Confirmed" ? "primary" : "outline"}
          disabled={busy}
          onClick={() =>
            s === "Cancelled" || s === "Lost"
              ? setAsk(s)
              : act(() => banquet.setStatus(fn.name, s))
          }
        >
          {s === "Confirmed"
            ? "Confirm"
            : s === "Completed"
              ? "Close out"
              : s === "Enquiry"
                ? "Reopen"
                : s}
        </Button>
      ))}
      {ask && (
        <Sheet
          title={ask === "Lost" ? "Mark this lost" : "Cancel this function"}
          description="The reason is what makes the pipeline worth reading later."
          onClose={() => setAsk(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAsk(null)}>
                Back
              </Button>
              <Button
                disabled={busy || !reason.trim()}
                onClick={async () => {
                  await act(() => banquet.setStatus(fn.name, ask, reason))
                  setAsk(null)
                  setReason("")
                }}
              >
                {ask === "Lost" ? "Mark lost" : "Cancel it"}
              </Button>
            </div>
          }
        >
          <Field label="What happened?">
            <textarea
              rows={4}
              className={inputCls}
              placeholder="Went to a competitor on price / date moved / event called off…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </Sheet>
      )}
    </div>
  )
}

/* ── the function itself ──────────────────────────────────────────────── */

function DetailTab({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [rooms, setRooms] = useState<Row[]>([])
  const dirty = Object.keys(draft).length > 0
  const get = <T,>(k: keyof FunctionSheet, fallback: T) =>
    (draft[k as string] ?? fn[k] ?? fallback) as T
  const set = (k: string, v: unknown) => setDraft((d) => ({ ...d, [k]: v }))

  useEffect(() => {
    setDraft({})
  }, [fn])

  useEffect(() => {
    listResource("Room", {
      fields: ["name", "room_number", "room_type"],
      orderBy: "room_number asc",
      limit: 300,
    })
      .then(setRooms)
      .catch(() => {})
  }, [])

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock className="size-4" />
                When & how the room is set
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Field label="Event name" className="sm:col-span-2">
              <input
                className={inputCls}
                placeholder="Sharma–Verma reception"
                value={get("event_name", "")}
                onChange={(e) => set("event_name", e.target.value)}
              />
            </Field>
            <Field label="Event type">
              <Select
                value={get("event_type", "Other")}
                onChange={(v) => set("event_type", v)}
                options={EVENT_TYPES}
              />
            </Field>
            <Field label="Setup style">
              <Select
                value={get("setup_style", "Round Table")}
                onChange={(v) => set("setup_style", v)}
                options={SETUP_STYLES}
              />
            </Field>
            <Field label="Date">
              <input
                type="date"
                className={inputCls}
                value={get("event_date", "")}
                onChange={(e) => set("event_date", e.target.value)}
              />
            </Field>
            <Field label="Ends" hint="Blank for a single day">
              <input
                type="date"
                className={inputCls}
                value={get("end_date", "")}
                onChange={(e) => set("end_date", e.target.value || null)}
              />
            </Field>
            <Field
              label="Session"
              hint="Halls sell by the session; pick Custom Hours to state your own"
            >
              <Select
                value={get<string>("session", "Evening")}
                onChange={(v) => set("session", v)}
                options={SESSIONS}
              />
            </Field>
            <Field label="From">
              <input
                type="time"
                className={inputCls}
                disabled={get<string>("session", "Evening") !== "Custom Hours"}
                value={String(get("start_time", "")).slice(0, 5)}
                onChange={(e) => set("start_time", e.target.value || null)}
              />
            </Field>
            <Field
              label="To"
              hint={
                fn.billable_hours
                  ? `${fn.billable_hours} billable hours`
                  : undefined
              }
            >
              <input
                type="time"
                className={inputCls}
                value={String(get("end_time", "")).slice(0, 5)}
                onChange={(e) => set("end_time", e.target.value || null)}
              />
            </Field>
            <Field label="Decorator can start" hint="Setup access">
              <input
                type="datetime-local"
                className={inputCls}
                value={String(get("setup_from", "")).replace(" ", "T").slice(0, 16)}
                onChange={(e) => set("setup_from", e.target.value || null)}
              />
            </Field>
            <Field label="Cleared by">
              <input
                type="datetime-local"
                className={inputCls}
                value={String(get("teardown_by", "")).replace(" ", "T").slice(0, 16)}
                onChange={(e) => set("teardown_by", e.target.value || null)}
              />
            </Field>
            <Field label="Setup notes" className="sm:col-span-2">
              <textarea
                rows={2}
                className={inputCls}
                placeholder="Stage 20×12 at the north end, dance floor centre, buffet along the east wall…"
                value={get("setup_notes", "")}
                onChange={(e) => set("setup_notes", e.target.value)}
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <Users className="size-4" />
                Pax & the customer
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Field label="Expected pax" hint="The working number">
              <input
                type="number"
                className={inputCls}
                value={get("attendees", 0)}
                onChange={(e) => set("attendees", Number(e.target.value) || 0)}
              />
            </Field>
            <Field
              label="Guaranteed pax"
              hint="The minimum they pay for - menus bill on this"
            >
              <input
                type="number"
                className={inputCls}
                value={get("pax_guaranteed", 0)}
                onChange={(e) =>
                  set("pax_guaranteed", Number(e.target.value) || 0)
                }
              />
            </Field>
            <Field label="Actual pax" hint="Counted on the day">
              <input
                type="number"
                className={inputCls}
                value={get("pax_actual", 0)}
                onChange={(e) => set("pax_actual", Number(e.target.value) || 0)}
              />
            </Field>
            <Field label="Billing on" hint={`${fn.billable_pax} pax`}>
              <Select
                value={get("rate_basis", "Per Pax")}
                onChange={(v) => set("rate_basis", v)}
                options={["Per Pax", "Per Plate", "Lump Sum", "Per Hour"]}
              />
            </Field>
            <Field label="Contact name">
              <input
                className={inputCls}
                value={get("customer_name", "")}
                onChange={(e) => set("customer_name", e.target.value)}
              />
            </Field>
            <Field label="Phone">
              <input
                className={inputCls}
                value={get("customer_phone", "")}
                onChange={(e) => set("customer_phone", e.target.value)}
              />
            </Field>
            <Field label="Email">
              <input
                className={inputCls}
                value={get("customer_email", "")}
                onChange={(e) => set("customer_email", e.target.value)}
              />
            </Field>
            <Field label="Came from">
              <Select
                value={get("source", "Phone")}
                onChange={(v) => set("source", v)}
                options={SOURCES}
              />
            </Field>
            <Field label="Next follow-up">
              <input
                type="date"
                className={inputCls}
                value={get("follow_up_date", "")}
                onChange={(e) => set("follow_up_date", e.target.value || null)}
              />
            </Field>
            {fn.status === "Tentative" && (
              <Field
                label="Hold expires"
                hint="After this the hall is sellable again"
              >
                <input
                  type="date"
                  className={inputCls}
                  value={get("tentative_until", "")}
                  onChange={(e) =>
                    set("tentative_until", e.target.value || null)
                  }
                />
              </Field>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Billing & {taxLabel()}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Field
              label="Invoice name"
              hint="If the legal name differs from the contact"
            >
              <input
                className={inputCls}
                value={get("billing_name", "")}
                onChange={(e) => set("billing_name", e.target.value)}
              />
            </Field>
            <Field label={`${taxLabel()} number`}>
              <input
                className={inputCls}
                placeholder="29AABCU9603R1ZM"
                value={get("gstin", "")}
                onChange={(e) => set("gstin", e.target.value.toUpperCase())}
              />
            </Field>
            <Field
              label="Place of supply"
              hint="Decides CGST+SGST vs IGST"
            >
              <input
                className={inputCls}
                placeholder="Karnataka"
                value={get("place_of_supply", "")}
                onChange={(e) => set("place_of_supply", e.target.value)}
              />
            </Field>
            <Field label="Contract signed on">
              <input
                type="date"
                className={inputCls}
                value={get("contract_signed_on", "")}
                onChange={(e) =>
                  set("contract_signed_on", e.target.value || null)
                }
              />
            </Field>
            <Field label="Billing address" className="sm:col-span-2">
              <textarea
                rows={2}
                className={inputCls}
                value={get("billing_address", "")}
                onChange={(e) => set("billing_address", e.target.value)}
              />
            </Field>
            {fn.group_detail && (
              <p className="sm:col-span-2 text-xs text-zinc-500">
                Tied to group{" "}
                <Link
                  className="font-medium text-brand-700 hover:underline"
                  to="/groups"
                >
                  {fn.group_detail.group_name}
                </Link>{" "}
                - the bill can ride its master folio.
              </p>
            )}
          </CardContent>
        </Card>

        <GreenRoomCard fn={fn} rooms={rooms} busy={busy} act={act} />

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-3">
            <Field label="What they asked for" hint="In the customer's words">
              <textarea
                rows={4}
                className={inputCls}
                value={get("requirements", "")}
                onChange={(e) => set("requirements", e.target.value)}
              />
            </Field>
            <Field
              label="Event order notes"
              hint="Prints for the banquet, kitchen and AV teams"
            >
              <textarea
                rows={4}
                className={inputCls}
                value={get("beo_notes", "")}
                onChange={(e) => set("beo_notes", e.target.value)}
              />
            </Field>
            <Field label="Internal" hint="Never printed on anything they see">
              <textarea
                rows={4}
                className={inputCls}
                value={get("internal_notes", "")}
                onChange={(e) => set("internal_notes", e.target.value)}
              />
            </Field>
          </CardContent>
        </Card>
      </div>

      {dirty && (
        <div className="sticky bottom-4 flex items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
          <span className="text-sm text-brand-900">
            {Object.keys(draft).length} unsaved change
            {Object.keys(draft).length === 1 ? "" : "s"}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setDraft({})}>
              Discard
            </Button>
            <Button
              disabled={busy}
              onClick={() => act(() => banquet.update(fn.name, draft))}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function GreenRoomCard({
  fn,
  rooms,
  busy,
  act,
}: {
  fn: FunctionSheet
  rooms: Row[]
  busy: boolean
  act: Act
}) {
  const [room, setRoom] = useState(fn.green_room ?? "")
  const [comp, setComp] = useState(Boolean(fn.green_room_complimentary))
  const [rate, setRate] = useState("")
  useEffect(() => {
    setRoom(fn.green_room ?? "")
    setComp(Boolean(fn.green_room_complimentary))
  }, [fn])

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="inline-flex items-center gap-1.5">
            <Gift className="size-4" />
            Green room
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-zinc-400">
          The changing room for the wedding party. Assigning one puts a room
          block on it, so it genuinely leaves the sellable inventory rather
          than living on a note.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Room">
            <select
              className={inputCls}
              value={room}
              onChange={(e) => setRoom(e.target.value)}
            >
              <option value="">None held</option>
              {rooms.map((r) => (
                <option key={r.name} value={r.name}>
                  {String(r.room_number)} · {String(r.room_type ?? "")}
                </option>
              ))}
            </select>
          </Field>
          <Field label="How it bills">
            <select
              className={inputCls}
              value={comp ? "comp" : "charge"}
              onChange={(e) => setComp(e.target.value === "comp")}
            >
              <option value="comp">Complimentary (house use)</option>
              <option value="charge">Charged as accommodation</option>
            </select>
          </Field>
          {!comp && (
            <Field label="Rate">
              <input
                type="number"
                className={inputCls}
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
            </Field>
          )}
        </div>
        <div className="flex items-center justify-between">
          {fn.green_room_block ? (
            <span className="text-xs text-emerald-700">
              Held out of sale ({fn.green_room_block})
            </span>
          ) : (
            <span className="text-xs text-zinc-400">Nothing held</span>
          )}
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(() =>
                banquet.assignGreenRoom(fn.name, {
                  room: room || null,
                  complimentary: comp ? 1 : 0,
                  rate: Number(rate) || 0,
                }),
              )
            }
          >
            {room ? "Hold it" : "Release"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/* ── the line items ───────────────────────────────────────────────────── */

function ItemsTab({
  fn,
  cat,
  busy,
  act,
}: {
  fn: FunctionSheet
  cat: BanquetCatalogue | null
  busy: boolean
  act: Act
}) {
  const [lines, setLines] = useState<FunctionItem[]>(fn.items)
  const [picker, setPicker] = useState<"menu" | "service" | null>(null)
  const [composing, setComposing] = useState<string | null>(null)
  const [discount, setDiscount] = useState(String(fn.discount_amount || ""))
  const [serviceCharge, setServiceCharge] = useState(
    String(fn.service_charge_percent || ""),
  )
  useEffect(() => {
    setLines(fn.items)
    setDiscount(String(fn.discount_amount || ""))
    setServiceCharge(String(fn.service_charge_percent || ""))
  }, [fn])

  const edit = (i: number, patch: Partial<FunctionItem>) =>
    setLines((ls) => ls.map((l, x) => (x === i ? { ...l, ...patch } : l)))

  const dirty = useMemo(
    () => JSON.stringify(lines) !== JSON.stringify(fn.items),
    [lines, fn.items],
  )
  const discountDirty = Number(discount || 0) !== Number(fn.discount_amount || 0)
  const serviceDirty =
    Number(serviceCharge || 0) !== Number(fn.service_charge_percent || 0)

  // what the quote would say if the open items all landed
  const openImpact = fn.open_item_impact

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>What they're buying</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setPicker("menu")}>
              <Plus className="size-4" />
              Menu
            </Button>
            <Button variant="outline" onClick={() => setPicker("service")}>
              <Plus className="size-4" />
              Service
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                setLines((ls) => [
                  ...ls,
                  {
                    name: `new-${ls.length}-${Date.now()}`,
                    item_type: "Other",
                    item_name: "",
                    banquet_menu: null,
                    service_item: null,
                    description: null,
                    qty: 1,
                    uom: "Lot",
                    list_rate: 0,
                    rate: 0,
                    chargeable: 1,
                    is_alcohol: 0,
                    on_pack_list: 0,
                    tax_exempt: 0,
                    amount: 0,
                    net_amount: 0,
                    gst_rate: 0,
                    gst_amount: 0,
                    total: 0,
                    notes: null,
                  },
                ])
              }
            >
              <Plus className="size-4" />
              Blank line
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {lines.length === 0 ? (
            <Empty>
              Nothing on the quote yet - add the menu and the extras.
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-[11px] uppercase tracking-wider text-zinc-400">
                    <th className="w-36 py-2 pr-2 font-medium">Type</th>
                    <th className="min-w-56 py-2 pr-2 font-medium">Item</th>
                    <th className="w-20 py-2 pr-2 text-right font-medium">Qty</th>
                    <th className="w-24 py-2 pr-2 font-medium">Per</th>
                    <th className="w-24 py-2 pr-2 text-right font-medium">Rack</th>
                    <th className="w-28 py-2 pr-2 text-right font-medium">Agreed</th>
                    <th className="w-16 py-2 pr-2 text-center font-medium">Charge</th>
                    <th className="w-20 py-2 pr-2 text-right font-medium">
                      {taxLabel()} %
                    </th>
                    <th className="w-28 py-2 pr-2 text-right font-medium">Amount</th>
                    <th className="w-8 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr
                      key={l.name}
                      className={
                        "border-b border-zinc-100 " +
                        (l.chargeable ? "" : "bg-zinc-50/60")
                      }
                    >
                      <td className="py-1.5 pr-2">
                        <select
                          className={inputCls + " !py-1"}
                          value={l.item_type}
                          onChange={(e) =>
                            edit(i, { item_type: e.target.value })
                          }
                        >
                          {ITEM_TYPES.map((t) => (
                            <option key={t}>{t}</option>
                          ))}
                        </select>
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          className={inputCls + " !py-1"}
                          value={l.item_name}
                          placeholder="What is it?"
                          onChange={(e) =>
                            edit(i, { item_name: e.target.value })
                          }
                        />
                        {l.banquet_menu && (
                          <button
                            className="mt-0.5 block text-[11px] font-medium text-brand-700 hover:underline"
                            onClick={() => setComposing(l.banquet_menu)}
                          >
                            {fn.selections?.some(
                              (x) => x.banquet_menu === l.banquet_menu,
                            )
                              ? "menu chosen · edit dishes"
                              : "choose the dishes →"}
                          </button>
                        )}
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          type="number"
                          className={inputCls + " !py-1 text-right"}
                          value={l.qty}
                          onChange={(e) =>
                            edit(i, { qty: Number(e.target.value) })
                          }
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        <select
                          className={inputCls + " !py-1"}
                          value={l.uom}
                          onChange={(e) => edit(i, { uom: e.target.value })}
                        >
                          {UOMS.map((u) => (
                            <option key={u}>{u}</option>
                          ))}
                        </select>
                      </td>
                      <td className="py-1.5 pr-2 text-right text-xs tabular-nums text-zinc-400">
                        {l.list_rate ? inr(l.list_rate) : "—"}
                      </td>
                      <td className="py-1.5 pr-2">
                        <input
                          type="number"
                          className={inputCls + " !py-1 text-right"}
                          value={l.rate}
                          onChange={(e) =>
                            edit(i, { rate: Number(e.target.value) })
                          }
                        />
                      </td>
                      <td className="py-1.5 pr-2 text-center">
                        <input
                          type="checkbox"
                          className="size-4 accent-brand-600"
                          checked={Boolean(l.chargeable)}
                          title={
                            l.chargeable
                              ? "Billed"
                              : "Complimentary - still on the event order and pack list"
                          }
                          onChange={(e) =>
                            edit(i, { chargeable: e.target.checked ? 1 : 0 })
                          }
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        {l.chargeable ? (
                          <input
                            type="number"
                            className={inputCls + " !py-1 text-right"}
                            title={
                              l.tax_exempt
                                ? "Zero-rated on purpose"
                                : `0 marks the line exempt; blank re-derives the rate for a ${l.item_type} line`
                            }
                            value={l.tax_exempt ? 0 : l.gst_rate || ""}
                            // 0 is a deliberate exemption, not a blank - without
                            // the flag the server would re-derive the rate for
                            // this kind of item and quietly tax it again
                            onChange={(e) => {
                              const n = Number(e.target.value)
                              edit(i, {
                                gst_rate: n,
                                tax_exempt: e.target.value !== "" && n === 0 ? 1 : 0,
                              })
                            }}
                          />
                        ) : (
                          <span className="block text-right text-zinc-400">-</span>
                        )}
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        {l.chargeable ? (
                          inr(l.net_amount || l.amount)
                        ) : (
                          <span className="text-zinc-400">
                            {inr(l.qty * l.rate)} free
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 text-right">
                        <button
                          className="text-zinc-300 hover:text-rose-600"
                          onClick={() =>
                            setLines((ls) => ls.filter((_, x) => x !== i))
                          }
                          aria-label="Remove line"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Discount on the whole quote">
                <input
                  type="number"
                  className={inputCls + " !w-40"}
                  value={discount}
                  onChange={(e) => setDiscount(e.target.value)}
                />
              </Field>
              <Field
                label="Service charge %"
                hint="On the food and the people serving it, not the hall"
              >
                <input
                  type="number"
                  className={inputCls + " !w-28"}
                  value={serviceCharge}
                  onChange={(e) => setServiceCharge(e.target.value)}
                />
              </Field>
              <p className="max-w-64 pb-2 text-xs text-zinc-400">
                The discount spreads pro-rata across the lines, so each keeps
                its own {taxLabel()} rate.
              </p>
            </div>
            <div className="min-w-56 space-y-1 text-sm">
              <Row label="Subtotal" value={inr(fn.subtotal)} />
              {fn.discount_amount > 0 && (
                <Row
                  label="Less discount"
                  value={"-" + inr(fn.discount_amount)}
                  tone="text-amber-700"
                />
              )}
              {fn.service_charge > 0 && (
                <Row
                  label={`Service charge ${fn.service_charge_percent}%`}
                  value={inr(fn.service_charge)}
                />
              )}
              <Row label="Taxable" value={inr(fn.taxable_amount)} />
              <Row label={taxLabel()} value={inr(fn.tax_amount)} />
              <Row
                label="Grand total"
                value={inr(fn.grand_total)}
                tone="font-semibold border-t border-zinc-200 pt-1"
              />
              {fn.non_chargeable_value > 0 && (
                <Row
                  label="Complimentary"
                  value={inr(fn.non_chargeable_value)}
                  tone="text-zinc-400"
                />
              )}
              {openImpact !== 0 && (
                <Row
                  label="If open items land"
                  value={inr(fn.grand_total + openImpact)}
                  tone="text-zinc-400"
                />
              )}
            </div>
          </div>

          {(dirty || discountDirty || serviceDirty) && (
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setLines(fn.items)
                  setDiscount(String(fn.discount_amount || ""))
                  setServiceCharge(String(fn.service_charge_percent || ""))
                }}
              >
                Discard
              </Button>
              <Button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    if (dirty)
                      await banquet.saveItems(
                        fn.name,
                        lines.filter((l) => l.item_name.trim()),
                      )
                    if (serviceDirty)
                      await banquet.update(fn.name, {
                        service_charge_percent: Number(serviceCharge) || 0,
                      })
                    if (discountDirty)
                      await banquet.negotiate(fn.name, {
                        discount_amount: Number(discount) || 0,
                      })
                  })
                }
              >
                Save &amp; reprice
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <OpenItemsCard fn={fn} busy={busy} act={act} />
      <RevisionsCard fn={fn} />

      {composing && (
        <MenuComposer
          fn={fn.name}
          menu={composing}
          pax={fn.billable_pax}
          onClose={() => setComposing(null)}
          onSaved={() => act(async () => {})}
        />
      )}

      {picker && cat && (
        <CataloguePicker
          kind={picker}
          cat={cat}
          onClose={() => setPicker(null)}
          onPick={async (id, chargeable) => {
            await act(() =>
              picker === "menu"
                ? banquet.addMenu(fn.name, id, { chargeable })
                : banquet.addService(fn.name, id, { chargeable }),
            )
            setPicker(null)
          }}
        />
      )}
    </div>
  )
}

function Row({
  label,
  value,
  tone = "",
}: {
  label: string
  value: string
  tone?: string
}) {
  return (
    <div className={"flex justify-between gap-6 " + tone}>
      <span className="text-zinc-500">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  )
}

function CataloguePicker({
  kind,
  cat,
  onClose,
  onPick,
}: {
  kind: "menu" | "service"
  cat: BanquetCatalogue
  onClose: () => void
  onPick: (id: string, chargeable: number) => void
}) {
  const [q, setQ] = useState("")
  const list =
    kind === "menu"
      ? cat.menus.filter((m) =>
          (m.menu_name + m.meal_period + (m.cuisine ?? ""))
            .toLowerCase()
            .includes(q.toLowerCase()),
        )
      : cat.services.filter((s) =>
          (s.item_name + s.category).toLowerCase().includes(q.toLowerCase()),
        )

  return (
    <Sheet
      title={kind === "menu" ? "Add a menu package" : "Add a service"}
      description={
        kind === "menu"
          ? "Priced per plate. The quantity follows the guaranteed pax."
          : "Projectors, LED walls, DJ, podium, stage, decor, bar. Add it free to give it away."
      }
      onClose={onClose}
      wide
    >
      <input
        className={inputCls + " mb-3"}
        placeholder="Search…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {list.length === 0 ? (
        <Empty>
          Nothing in the catalogue yet - build it under Banquet Catalogue.
        </Empty>
      ) : (
        <ul className="space-y-2">
          {list.map((item) => {
            const isMenu = "rate_per_pax" in item
            const rate = isMenu ? item.rate_per_pax : item.rate
            return (
              <li
                key={item.name}
                className="rounded-lg border border-zinc-200 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {isMenu ? item.menu_name : item.item_name}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {isMenu
                        ? `${item.meal_period} · ${item.food_type} · ${item.service_style}` +
                          (item.min_pax ? ` · min ${item.min_pax} pax` : "")
                        : `${item.category} · ${item.uom}` +
                          (item.chargeable ? "" : " · normally free")}
                    </p>
                    {isMenu && item.courses.length > 0 && (
                      <p className="mt-1 line-clamp-2 text-xs text-zinc-500">
                        {item.courses
                          .map((c) => `${c.course}: ${c.dishes ?? ""}`)
                          .join(" · ")}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="tabular-nums">{inr(rate)}</p>
                    <div className="mt-1 flex gap-1">
                      <Button
                        className="!px-2 !py-1 !text-xs"
                        onClick={() => onPick(item.name, 1)}
                      >
                        Add
                      </Button>
                      <Button
                        variant="outline"
                        className="!px-2 !py-1 !text-xs"
                        onClick={() => onPick(item.name, 0)}
                        title="Goes on the event order and pack list, not the quote"
                      >
                        Free
                      </Button>
                    </div>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Sheet>
  )
}

function OpenItemsCard({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  const [rows, setRows] = useState<Partial<OpenItem>[]>(fn.open_items)
  useEffect(() => setRows(fn.open_items), [fn])
  const dirty = JSON.stringify(rows) !== JSON.stringify(fn.open_items)
  const edit = (i: number, patch: Partial<OpenItem>) =>
    setRows((rs) => rs.map((r, x) => (x === i ? { ...r, ...patch } : r)))

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="inline-flex items-center gap-1.5">
            <Handshake className="size-4" />
            Open items
          </span>
        </CardTitle>
        <Button
          variant="outline"
          onClick={() =>
            setRows((rs) => [
              ...rs,
              {
                title: "",
                owner_side: "Hotel",
                status: "Open",
                price_impact: 0,
              },
            ])
          }
        >
          <Plus className="size-4" />
          Add
        </Button>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-zinc-400">
          What's still unsettled while the price is being agreed - and what
          agreeing it would do to the quote.
        </p>
        {rows.length === 0 ? (
          <Empty>Nothing outstanding.</Empty>
        ) : (
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div
                key={i}
                className="grid gap-2 rounded-lg border border-zinc-200 px-3 py-2 sm:grid-cols-[1fr_auto_auto_auto_auto]"
              >
                <input
                  className={inputCls}
                  placeholder="Sangeet stage - who pays?"
                  value={r.title ?? ""}
                  onChange={(e) => edit(i, { title: e.target.value })}
                />
                <select
                  className={inputCls + " sm:!w-28"}
                  value={r.owner_side ?? "Hotel"}
                  onChange={(e) =>
                    edit(i, { owner_side: e.target.value as "Hotel" | "Client" })
                  }
                >
                  <option>Hotel</option>
                  <option>Client</option>
                </select>
                <input
                  type="date"
                  className={inputCls + " sm:!w-36"}
                  value={r.due_date ?? ""}
                  onChange={(e) => edit(i, { due_date: e.target.value || null })}
                />
                <input
                  type="number"
                  className={inputCls + " sm:!w-28 text-right"}
                  placeholder="Impact"
                  value={r.price_impact ?? 0}
                  onChange={(e) =>
                    edit(i, { price_impact: Number(e.target.value) })
                  }
                />
                <select
                  className={inputCls + " sm:!w-28"}
                  value={r.status ?? "Open"}
                  onChange={(e) =>
                    edit(i, {
                      status: e.target.value as OpenItem["status"],
                    })
                  }
                >
                  <option>Open</option>
                  <option>Agreed</option>
                  <option>Dropped</option>
                </select>
              </div>
            ))}
          </div>
        )}
        {dirty && (
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setRows(fn.open_items)}>
              Discard
            </Button>
            <Button
              disabled={busy}
              onClick={() =>
                act(() =>
                  banquet.saveOpenItems(
                    fn.name,
                    rows.filter((r) => (r.title ?? "").trim()),
                  ),
                )
              }
            >
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function RevisionsCard({ fn }: { fn: FunctionSheet }) {
  if (fn.revisions.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>How the price moved</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-2">
          {[...fn.revisions].reverse().map((r) => (
            <li key={r.name} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-500">
                v{r.version}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-zinc-700">{r.change_note}</p>
                <p className="text-xs text-zinc-400">
                  {String(r.revised_on).slice(0, 16)} · {r.revised_by} ·{" "}
                  {r.pax} pax
                </p>
              </div>
              <span className="shrink-0 tabular-nums">{inr(r.grand_total)}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

/* ── terms, receipts, settlement ──────────────────────────────────────── */

function MoneyTab({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  const [terms, setTerms] = useState<Partial<PaymentTerm>[]>(fn.payment_terms)
  const [note, setNote] = useState(fn.payment_terms_note ?? "")
  const [receipt, setReceipt] = useState<{
    amount: string
    mode: string
    kind: string
    reference: string
    settle_term: string
  } | null>(null)
  const [receiptDoc, setReceiptDoc] = useState<string | null>(null)
  useEffect(() => {
    setTerms(fn.payment_terms)
    setNote(fn.payment_terms_note ?? "")
  }, [fn])

  const dirty =
    JSON.stringify(terms) !== JSON.stringify(fn.payment_terms) ||
    note !== (fn.payment_terms_note ?? "")
  const edit = (i: number, patch: Partial<PaymentTerm>) =>
    setTerms((ts) => ts.map((t, x) => (x === i ? { ...t, ...patch } : t)))
  const scheduled = terms.reduce((s, t) => s + Number(t.amount || 0), 0)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Payment terms</CardTitle>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => act(() => banquet.defaultPaymentTerms(fn.name))}
            >
              Use the usual schedule
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                setTerms((ts) => [
                  ...ts,
                  { milestone: "", percent: 0, amount: 0, status: "Pending" },
                ])
              }
            >
              <Plus className="size-4" />
              Add
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {terms.length === 0 ? (
            <Empty>
              No schedule yet - the usual one is an advance, a call before the
              date, and the rest on completion.
            </Empty>
          ) : (
            <div className="space-y-2">
              {terms.map((t, i) => (
                <div
                  key={i}
                  className="grid gap-2 rounded-lg border border-zinc-200 px-3 py-2 sm:grid-cols-[1fr_auto_auto_auto_auto]"
                >
                  <input
                    className={inputCls}
                    placeholder="Booking advance"
                    value={t.milestone ?? ""}
                    onChange={(e) => edit(i, { milestone: e.target.value })}
                  />
                  <input
                    type="date"
                    className={inputCls + " sm:!w-36"}
                    value={t.due_date ?? ""}
                    onChange={(e) =>
                      edit(i, { due_date: e.target.value || null })
                    }
                  />
                  <input
                    type="number"
                    className={inputCls + " sm:!w-20 text-right"}
                    placeholder="%"
                    value={t.percent ?? ""}
                    onChange={(e) =>
                      edit(i, { percent: Number(e.target.value), amount: 0 })
                    }
                  />
                  <input
                    type="number"
                    className={inputCls + " sm:!w-32 text-right"}
                    placeholder="Amount"
                    value={t.amount ?? ""}
                    onChange={(e) => edit(i, { amount: Number(e.target.value) })}
                  />
                  <select
                    className={
                      inputCls +
                      " sm:!w-28 " +
                      (t.status === "Overdue" ? "!text-rose-700" : "")
                    }
                    value={t.status ?? "Pending"}
                    onChange={(e) =>
                      edit(i, { status: e.target.value as PaymentTerm["status"] })
                    }
                  >
                    <option>Pending</option>
                    <option>Overdue</option>
                    <option>Received</option>
                    <option>Waived</option>
                  </select>
                </div>
              ))}
              <p className="pt-1 text-xs text-zinc-400">
                Scheduled {inr(scheduled)} of {inr(fn.grand_total)}
                {Math.abs(scheduled - fn.grand_total) > 1 && (
                  <span className="text-amber-700">
                    {" "}
                    · {inr(Math.abs(scheduled - fn.grand_total))}{" "}
                    {scheduled > fn.grand_total ? "over" : "unscheduled"}
                  </span>
                )}
              </p>
            </div>
          )}
          <Field
            label="Terms & policy"
            hint="Cancellation, retention, taxes-extra wording - prints on the contract"
            className="mt-3"
          >
            <textarea
              rows={3}
              className={inputCls}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          {dirty && (
            <div className="mt-3 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setTerms(fn.payment_terms)
                  setNote(fn.payment_terms_note ?? "")
                }}
              >
                Discard
              </Button>
              <Button
                disabled={busy}
                onClick={() =>
                  act(() =>
                    banquet.setPaymentTerms(
                      fn.name,
                      terms.filter((t) => (t.milestone ?? "").trim()),
                      note,
                    ),
                  )
                }
              >
                Save terms
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <span className="inline-flex items-center gap-1.5">
              <Receipt className="size-4" />
              Receipts
            </span>
          </CardTitle>
          <Button
            onClick={() =>
              setReceipt({
                amount: "",
                mode: "Bank Transfer",
                kind: "Advance",
                reference: "",
                settle_term: "",
              })
            }
          >
            <Plus className="size-4" />
            Record money in
          </Button>
        </CardHeader>
        <CardContent>
          {fn.receipts.length === 0 ? (
            <Empty>Nothing received yet.</Empty>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {fn.receipts.map((r) => (
                  <tr key={r.name} className="group border-b border-zinc-100">
                    <td className="py-2 tabular-nums text-zinc-500">
                      {r.receipt_date}
                    </td>
                    <td className="py-2">
                      {r.kind}
                      {r.kind === "Security Deposit" && (
                        <span className="ml-1.5 rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
                          held
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-zinc-500">{r.mode}</td>
                    <td className="py-2 text-zinc-400">{r.reference}</td>
                    <td
                      className={
                        "py-2 text-right tabular-nums " +
                        (r.kind === "Refund" ? "text-rose-700" : "")
                      }
                    >
                      {r.kind === "Refund" ? "-" : ""}
                      {inr(r.amount)}
                    </td>
                    <td className="w-8 py-2 text-right">
                      {/* every advance a banquet office takes needs a piece
                          of paper against it */}
                      <button
                        title="Print this receipt"
                        aria-label="Print this receipt"
                        className="text-zinc-300 opacity-0 transition-opacity hover:text-brand-700 group-hover:opacity-100"
                        onClick={() => setReceiptDoc(r.name)}
                      >
                        <Printer className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-3 flex justify-end gap-6 text-sm">
            <Row label="Received" value={inr(fn.advance_received)} />
            <Row
              label="Balance"
              value={inr(fn.balance_due)}
              tone={fn.balance_due > 0 ? "text-rose-700" : "text-emerald-700"}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <span className="inline-flex items-center gap-1.5">
              <BadgeIndianRupee className="size-4" />
              Settlement
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {fn.posted_to_folio ? (
            <p className="text-sm text-emerald-700">
              Billed to folio{" "}
              <Link
                className="font-medium hover:underline"
                to={`/billing/${encodeURIComponent(fn.folio ?? "")}`}
              >
                {fn.folio}
              </Link>
              .
            </p>
          ) : (
            <>
              <p className="text-sm text-zinc-500">
                {fn.group_detail
                  ? `Posts to ${fn.group_detail.group_name}'s master folio - one bill for the rooms and the function.`
                  : "Tie this function to a group booking to bill it onto the group's master folio."}
              </p>
              <Button
                disabled={busy || !fn.group_booking || fn.status === "Enquiry"}
                onClick={() => act(() => banquet.postToFolio(fn.name))}
              >
                Post to the bill
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {receiptDoc && (
        <ReceiptPrint
          fn={fn.name}
          receipt={receiptDoc}
          onClose={() => setReceiptDoc(null)}
        />
      )}

      {receipt && (
        <Sheet
          title="Record money in"
          onClose={() => setReceipt(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setReceipt(null)}>
                Cancel
              </Button>
              <Button
                disabled={busy || !Number(receipt.amount)}
                onClick={async () => {
                  await act(() =>
                    banquet.recordReceipt(fn.name, {
                      amount: Number(receipt.amount),
                      mode: receipt.mode,
                      kind: receipt.kind,
                      reference: receipt.reference || null,
                      settle_term: receipt.settle_term || null,
                    }),
                  )
                  setReceipt(null)
                }}
              >
                Record it
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <Field label="Amount">
              <input
                type="number"
                className={inputCls}
                value={receipt.amount}
                onChange={(e) =>
                  setReceipt({ ...receipt, amount: e.target.value })
                }
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="What is it">
                <Select
                  value={receipt.kind}
                  onChange={(v) => setReceipt({ ...receipt, kind: v })}
                  options={["Advance", "Payment", "Security Deposit", "Refund"]}
                />
              </Field>
              <Field label="How">
                <Select
                  value={receipt.mode}
                  onChange={(v) => setReceipt({ ...receipt, mode: v })}
                  options={PAY_MODES}
                />
              </Field>
            </div>
            <Field label="Reference" hint="UTR, cheque number, card slip">
              <input
                className={inputCls}
                value={receipt.reference}
                onChange={(e) =>
                  setReceipt({ ...receipt, reference: e.target.value })
                }
              />
            </Field>
            {fn.payment_terms.some((t) => t.status !== "Received") && (
              <Field label="Ticks off which milestone">
                <select
                  className={inputCls}
                  value={receipt.settle_term}
                  onChange={(e) =>
                    setReceipt({ ...receipt, settle_term: e.target.value })
                  }
                >
                  <option value="">None</option>
                  {fn.payment_terms
                    .filter((t) => t.status !== "Received")
                    .map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.milestone} · {inr(t.amount)}
                      </option>
                    ))}
                </select>
              </Field>
            )}
          </div>
        </Sheet>
      )}
    </div>
  )
}

/* ── handing the hall back ────────────────────────────────────────────── */

/** The last ritual of a function, and the one that usually happens on a
 *  WhatsApp message and a scrap of paper: walk the room, count what
 *  actually turned up, note what got broken, take that off the deposit and
 *  give the rest back. Doing it in one motion means the deduction carries
 *  a reason and the refund is a real ledger line. */
function CloseOutCard({
  fn,
  busy,
  act,
  onCount,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
  onCount?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [pax, setPax] = useState(String(fn.pax_actual || fn.pax_guaranteed || ""))
  const [damage, setDamage] = useState("")
  const [note, setNote] = useState("")
  const [refund, setRefund] = useState(true)
  const [mode, setMode] = useState("Bank Transfer")

  const held = fn.deposit_held || 0
  const willRefund = refund ? Math.max(0, held - (Number(damage) || 0)) : 0
  const done = Boolean(fn.closed_out_on)

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="size-4" />
            Deposit &amp; close-out
          </span>
        </CardTitle>
        <div className="flex gap-2">
          {onCount && (
            <Button variant="outline" onClick={onCount}>
              Count what was served
            </Button>
          )}
          {!done && fn.status === "Confirmed" && (
            <Button onClick={() => setOpen(true)}>Close out the function</Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <Money label="Deposit held" value={held} tone="text-violet-700" />
          <Money
            label="Damages"
            value={fn.damage_amount}
            sub={fn.damage_note ?? undefined}
            tone={fn.damage_amount ? "text-rose-700" : "text-zinc-400"}
          />
          <Money
            label="Returned"
            value={fn.deposit_refunded}
            tone="text-emerald-700"
          />
        </div>
        {done ? (
          <p className="text-sm text-emerald-700">
            Closed out {String(fn.closed_out_on).slice(0, 16).replace("T", " ")}
            {fn.closed_out_by ? ` by ${fn.closed_out_by}` : ""}.
          </p>
        ) : (
          <p className="text-xs text-zinc-400">
            A security deposit is held money, not payment — it never nets
            against the bill. Record it as a Security Deposit receipt, then
            close out to return what's left after damages.
          </p>
        )}
      </CardContent>

      {open && (
        <Sheet
          title="Close out the function"
          description="Walk the room, count the covers, note the damage. One motion."
          onClose={() => setOpen(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Not yet
              </Button>
              <Button
                disabled={busy || (!!Number(damage) && !note.trim())}
                onClick={async () => {
                  await act(() =>
                    banquet.closeOut(fn.name, {
                      pax_actual: Number(pax) || null,
                      damage_amount: Number(damage) || 0,
                      damage_note: note || null,
                      refund_deposit: refund ? 1 : 0,
                      refund_mode: mode,
                    }),
                  )
                  setOpen(false)
                }}
              >
                Close it out
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <Field
              label="Covers actually served"
              hint={`Guaranteed ${fn.pax_guaranteed || 0}. The bill uses whichever is higher.`}
            >
              <input
                type="number"
                className={inputCls}
                value={pax}
                onChange={(e) => setPax(e.target.value)}
              />
            </Field>

            <div className="rounded-xl border border-zinc-200 p-3">
              <p className="mb-2 text-sm font-medium">Anything broken?</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Deduct from the deposit">
                  <input
                    type="number"
                    className={inputCls}
                    placeholder="0"
                    value={damage}
                    onChange={(e) => setDamage(e.target.value)}
                  />
                </Field>
                <Field label="Return the rest by">
                  <Select value={mode} onChange={setMode} options={PAY_MODES} />
                </Field>
              </div>
              {!!Number(damage) && (
                <Field
                  label="What was damaged"
                  hint="Required — a deduction the customer can't see the reason for is a dispute waiting"
                  className="mt-2"
                >
                  <textarea
                    rows={2}
                    className={inputCls}
                    placeholder="Two chairs and a table lamp in the pre-function area"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </Field>
              )}
            </div>

            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-brand-600"
                checked={refund}
                onChange={(e) => setRefund(e.target.checked)}
              />
              <span>
                <span className="block text-sm font-medium text-zinc-700">
                  Return the deposit balance now
                </span>
                <span className="block text-xs text-zinc-400">
                  Recorded as a refund on the function's ledger.
                </span>
              </span>
            </label>

            <div className="space-y-1 rounded-xl bg-zinc-50 px-4 py-3 text-sm">
              <Row label="Deposit held" value={inr(held)} />
              {!!Number(damage) && (
                <Row
                  label="Less damages"
                  value={"-" + inr(Number(damage))}
                  tone="text-rose-700"
                />
              )}
              <Row
                label="Returning"
                value={inr(willRefund)}
                tone="font-semibold border-t border-zinc-200 pt-1"
              />
              {!!Number(damage) && (
                <p className="pt-2 text-xs text-zinc-500">
                  The {inr(Number(damage))} deducted goes on the bill as a
                  damage-recovery line — it's the hotel's money now, not a
                  deposit.
                </p>
              )}
            </div>
          </div>
        </Sheet>
      )}
    </Card>
  )
}

/* ── the paper ────────────────────────────────────────────────────────── */

function PaperTab({
  fn,
  busy,
  act,
}: {
  fn: FunctionSheet
  busy: boolean
  act: Act
}) {
  const docs: {
    kind: string
    title: string
    blurb: string
    ready: boolean
    why?: string
  }[] = [
    {
      kind: "quote",
      title: "Quotation",
      blurb: "What it costs, line by line, with the terms.",
      ready: fn.items.length > 0,
      why: "Put some lines on it first.",
    },
    {
      kind: "contract",
      title: "Contract",
      blurb: "The quote, the schedule, the policy and the signature blocks.",
      ready: fn.items.length > 0,
      why: "Put some lines on it first.",
    },
    {
      kind: "beo",
      title: "Event order (BEO)",
      blurb: "The running sheet the banquet, kitchen and AV teams work from.",
      ready: fn.status === "Confirmed" || fn.status === "Completed",
      why: "Only a confirmed function gets an event order.",
    },
    {
      kind: "pack_list",
      title: "Pack list",
      blurb: "What physically has to reach the hall, and by when.",
      ready: fn.items.some((i) => i.on_pack_list),
      why: "No line is marked as something to carry yet.",
    },
    {
      kind: "invoice",
      title: "Invoice",
      blurb: "The bill against what's already been received.",
      ready: fn.status === "Confirmed" || fn.status === "Completed",
      why: "Confirm the function first.",
    },
  ]

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {docs.map((d) => (
          <Card key={d.kind}>
            <CardContent>
              <p className="flex items-center gap-1.5 font-medium">
                <FileText className="size-4 text-zinc-400" />
                {d.title}
              </p>
              <p className="mt-1 min-h-10 text-xs text-zinc-400">{d.blurb}</p>
              {d.ready ? (
                <Link
                  to={`/banquet/${encodeURIComponent(fn.name)}/${d.kind}`}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
                >
                  Open
                </Link>
              ) : (
                <p className="mt-2 text-xs text-amber-700">{d.why}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Issue</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button
            disabled={busy || fn.items.length === 0}
            onClick={() => act(() => banquet.generateQuote(fn.name))}
          >
            Stamp quote v{(fn.quote_version || 0) + 1}
          </Button>
          <Button
            variant="outline"
            disabled={busy || (fn.status !== "Confirmed" && fn.status !== "Completed")}
            onClick={() => act(() => banquet.generateBeo(fn.name))}
          >
            {fn.beo_number ? "Reissue event order" : "Issue event order"}
          </Button>
          <div className="text-xs text-zinc-400">
            {fn.quote_sent_on
              ? `Quote v${fn.quote_version} sent ${fn.quote_sent_on}${
                  fn.quote_valid_till ? `, valid till ${fn.quote_valid_till}` : ""
                }.`
              : "No quote issued yet."}
            {fn.beo_number && ` Event order ${fn.beo_number}.`}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

/* ── the receipt ──────────────────────────────────────────────────────── */

/** A receipt the customer can keep. A banquet office takes money weeks or
 *  months before the event, and "we've got your advance" is not a document —
 *  this is. Printed straight from the drawer so there's no extra journey. */
function ReceiptPrint({
  fn,
  receipt,
  onClose,
}: {
  fn: string
  receipt: string
  onClose: () => void
}) {
  const [doc, setDoc] = useState<ReceiptDocument | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    banquet
      .receiptDocument(fn, receipt)
      .then(setDoc)
      .catch((e) => setError(serverError(e)))
  }, [fn, receipt])

  return (
    <Sheet
      title="Receipt"
      description="Print it, or send the PDF straight from the print dialog."
      onClose={onClose}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button disabled={!doc} onClick={() => window.print()}>
            <Printer className="size-4" />
            Print
          </Button>
        </div>
      }
    >
      <ErrorNote error={error} />
      {!doc ? (
        <Empty>Loading…</Empty>
      ) : (
        <article className="mx-auto max-w-xl rounded-xl border border-zinc-200 px-8 py-6 text-sm print:border-0">
          <header className="border-b border-zinc-200 pb-3 text-center">
            <h1 className="text-base font-semibold">
              {doc.property.property_name ?? doc.property.legal_name}
            </h1>
            <p className="mt-0.5 text-xs text-zinc-500">
              {[doc.property.address_line, doc.property.city]
                .filter(Boolean)
                .join(", ")}
              {doc.property.phone ? ` · ${doc.property.phone}` : ""}
            </p>
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.25em] text-zinc-400">
              {doc.header.title}
            </p>
          </header>

          <dl className="mt-4 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
            {(
              [
                ["Receipt no", doc.header.receipt_no.slice(-10)],
                ["Date", doc.header.date],
                ["Function", String(doc.event.function ?? "")],
                ["Customer", String(doc.customer.name ?? "")],
                ["Event", String(doc.event.event_name || doc.event.event_type || "")],
                [
                  "Hall / session",
                  `${doc.event.venue ?? ""} · ${doc.event.session ?? ""}`,
                ],
                ["Function date", String(doc.event.event_date ?? "")],
                ["Received by", doc.receipt.received_by ?? ""],
              ] as [string, string][]
            )
              .filter(([, v]) => v && v.trim() && v.trim() !== "·")
              .map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <dt className="w-28 shrink-0 text-zinc-400">{k}</dt>
                  <dd className="font-medium">{v}</dd>
                </div>
              ))}
          </dl>

          <div className="mt-5 rounded-lg bg-zinc-50 px-4 py-3">
            <div className="flex items-baseline justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-zinc-400">
                  {doc.receipt.kind} · {doc.receipt.mode}
                </p>
                {doc.receipt.reference && (
                  <p className="text-xs text-zinc-500">
                    {doc.receipt.reference}
                  </p>
                )}
              </div>
              <p className="text-2xl font-semibold tabular-nums">
                {inr(doc.receipt.amount)}
              </p>
            </div>
            <p className="mt-2 text-xs italic text-zinc-500">
              {doc.header.amount_in_words}
            </p>
          </div>

          <dl className="mt-4 space-y-1 text-xs">
            <RunLine label="Function total" value={doc.running.grand_total} />
            <RunLine label="Received to date" value={doc.running.received} />
            {doc.running.deposit_held > 0 && (
              <RunLine
                label="Refundable deposit held"
                value={doc.running.deposit_held}
              />
            )}
            <RunLine
              label="Balance due"
              value={doc.running.balance_due}
              bold
            />
          </dl>

          <div className="mt-10 grid grid-cols-2 gap-12">
            <div className="text-center">
              <div className="h-10 border-b border-zinc-400" />
              <p className="mt-1 text-[11px] text-zinc-400">Customer</p>
            </div>
            <div className="text-center">
              <div className="h-10 border-b border-zinc-400" />
              <p className="mt-1 text-[11px] text-zinc-400">
                For {doc.property.property_name}
              </p>
            </div>
          </div>
        </article>
      )}
    </Sheet>
  )
}

function RunLine({
  label,
  value,
  bold,
}: {
  label: string
  value: number
  bold?: boolean
}) {
  return (
    <div
      className={
        "flex justify-between " +
        (bold ? "border-t border-zinc-200 pt-1 font-semibold" : "text-zinc-500")
      }
    >
      <dt>{label}</dt>
      <dd className="tabular-nums">{inr(value)}</dd>
    </div>
  )
}
