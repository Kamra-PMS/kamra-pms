/*  The POS side panel: the outlet's orders (today, a past day, search,
    state filter, open one to view or reprint) and who the bill is for
    (in-house guest with the room-charge decision, or a walk-in customer
    found or added by phone or name, with their past bills here). It slides
    over the till, so the captain never leaves the POS. Everything comes
    from kamra.pos (orders_list, order_detail, guest_panel, find_customer,
    attach_customer), which scope it to the outlet and hide what service
    does not need (phones show last digits, no ID data). */

import { useCallback, useEffect, useRef, useState } from "react"
import {
  ArrowLeft, BedDouble, Download, FileSpreadsheet, History, ListOrdered, Phone, Receipt,
  Search, Star, UserPlus, UserRound, XCircle,
} from "lucide-react"
import { call } from "../../lib/api"
import { serverError } from "../../lib/resource"
import { cur, moneyLocale } from "../../lib/money"
import { useT } from "../../lib/i18n"
import { cn } from "../../lib/utils"
import { Button } from "../../components/ui/button"
import { billHtml, printThermal, type BillData } from "../../lib/thermal"

export type ListState = "open" | "sent" | "paid" | "room" | "nc" | "closed" | "cancelled"

interface ListRow {
  name: string
  label: string
  state: ListState
  order_type: string | null
  table_no: string | null
  room_no: string | null
  who: string | null
  amount: number
  items: number
  voided: number
  kot_no: number | null
  payment_mode: string | null
  guests: number | null
  time: string
  age_min: number
  stale: 0 | 1
  carried: 0 | 1
  cancel_reason: string | null
}
interface ListOut {
  from: string
  to: string
  rows: ListRow[]
  counts: Record<ListState, number>
}
interface ViewItem {
  row: string
  item_name: string
  qty: number
  amount: number
  kot_status: string
  voided: number
  void_reason: string | null
  voided_by?: string | null
  void_approved_by?: string | null
}
interface ViewDetail {
  name: string
  state: ListState
  status: string
  creation: string
  table_no: string | null
  room: string | null
  order_type: string | null
  kot_no: number | null
  customer_name: string | null
  paid: number
  payment_mode: string | null
  nc: number
  nc_authorized_by: string | null
  discount_amount: number
  subtotal: number
  order_total: number
  cancel_reason: string | null
  cancelled_by: string | null
  cancelled_at: string | null
  cancel_approved_by: string | null
  items: ViewItem[]
}

export interface GuestPanelData {
  kind: "none" | "in_house" | "customer"
  guest?: {
    name: string
    full_name: string
    vip: number
    category: string | null
    notes: string | null
    phone: string | null
  } | null
  allergy_note?: string | null
  stay?: {
    reservation: string
    guest_name: string | null
    room_number: string | null
    status: string
    check_in_date: string
    check_out_date: string
    room_charges_allowed: 0 | 1
  } | null
  history?: {
    visits: number
    bills: number
    spend: number
    last_visit: string | null
    orders: { name: string; time: string; amount: number; state: ListState; label: string; items: string }[]
  }
}
interface CustomerHit {
  guest: string
  full_name: string
  vip: number
  phone: string | null
  visits: number
  in_house_room: string | null
}

export const money = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })

const BADGE: Record<ListState, string> = {
  open: "bg-amber-100 text-amber-900",
  sent: "bg-sky-100 text-sky-900",
  paid: "bg-emerald-100 text-emerald-800",
  room: "bg-violet-100 text-violet-800",
  nc: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  closed: "bg-zinc-100 text-zinc-600",
  cancelled: "bg-rose-100 text-rose-700",
}
export const STATES: ListState[] = ["open", "sent", "paid", "room", "nc", "cancelled", "closed"]

/** yyyy-mm-dd for the device's own day */
export function localDay(d = new Date()) {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
export const hhmm = (ts?: string | null) => (ts ? ts.slice(11, 16) : "")
const dayOf = (ts?: string | null) => (ts ? ts.slice(0, 10) : "")
export function shortDay(d: string) {
  if (!d) return ""
  const dt = new Date(`${d}T00:00:00`)
  return isNaN(dt.getTime()) ? d : dt.toLocaleDateString(moneyLocale(), { day: "numeric", month: "short" })
}

export function useStateLabel() {
  const { t } = useT()
  return useCallback((s: ListState) => ({
    open: t("Not sent"),
    sent: t("In kitchen"),
    paid: t("Paid"),
    room: t("Posted to room"),
    nc: t("Complimentary"),
    closed: t("Closed"),
    cancelled: t("Cancelled"),
  })[s], [t])
}

export function StateBadge({ state, className }: { state: ListState; className?: string }) {
  const label = useStateLabel()
  return (
    <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-semibold", BADGE[state], className)}>
      {label(state)}
    </span>
  )
}

export default function PosSidePanel({
  outlet, tab, onTab, onClose, refreshKey, order, draft, onDraftGuest, onOpenBill, onGuestChanged, onHistory,
}: {
  outlet: string
  tab: "orders" | "guest"
  onTab: (t: "orders" | "guest") => void
  onClose: () => void
  /** bumps when the till sees a change, so the list follows live */
  refreshKey: number
  /** the bill on the till, or null for a new bill */
  order: string | null
  /** a new bill's room or chosen customer, before it exists */
  draft: { room: string | null; guest: string | null }
  onDraftGuest: (g: { guest: string; full_name: string } | null) => void
  onOpenBill: (name: string) => void
  onGuestChanged: () => void
  /** open the full-screen order history */
  onHistory?: () => void
}) {
  const { t } = useT()
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])
  const wide = tab === "orders"
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onClose} />
      <aside role="dialog" aria-label={tab === "orders" ? t("Orders") : t("Guest")}
        className={cn(
          "absolute inset-y-0 end-0 flex flex-col border-s border-zinc-200 bg-zinc-50 shadow-2xl animate-sheet-in",
          wide
            ? "w-full md:w-[min(100%,75vw)] xl:w-[min(100%,80rem)]"
            : "w-full sm:w-[28rem]",
        )}>
        <div className="flex shrink-0 items-center gap-2 border-b border-zinc-100 bg-white px-4 py-3">
          <div className={cn("flex rounded-xl border border-zinc-200 bg-zinc-50 p-1", wide ? "w-auto" : "flex-1")}>
            {([["orders", t("Orders"), ListOrdered], ["guest", t("Guest"), UserRound]] as const).map(([k, l, Icon]) => (
              <button key={k} onClick={() => onTab(k)}
                className={cn("flex items-center justify-center gap-1.5 rounded-lg px-3 py-2.5 text-sm font-semibold transition",
                  wide ? "px-4" : "flex-1",
                  tab === k ? "bg-brand-600 text-white shadow-sm" : "text-zinc-600 hover:bg-white")}>
                <Icon className="size-4" />{l}
              </button>
            ))}
          </div>
          {wide && (
            <h2 className="ms-1 hidden min-w-0 flex-1 truncate text-base font-semibold text-zinc-800 sm:block">
              {t("Orders history")}
            </h2>
          )}
          <button onClick={onClose} aria-label={t("Close")}
            className="ms-auto rounded-xl p-2.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700">
            <XCircle className="size-5" />
          </button>
        </div>
        <div className={cn(
          "min-h-0 flex-1",
          wide ? "flex flex-col overflow-hidden p-4 sm:p-5" : "overflow-y-auto p-4",
        )}>
          {tab === "orders"
            ? <OrdersTab outlet={outlet} refreshKey={refreshKey} onOpenBill={onOpenBill} onHistory={onHistory} />
            : <GuestTab outlet={outlet} order={order} draft={draft} refreshKey={refreshKey}
                onDraftGuest={onDraftGuest} onChanged={onGuestChanged} />}
        </div>
      </aside>
    </div>
  )
}

/* ── orders ─────────────────────────────────────────────────────────── */

const EXPORT_COLS = [
  "Bill", "Time", "Label", "State", "Type", "Table", "Room", "Customer",
  "Amount", "Items", "Voided", "KOT", "Payment", "Guests", "Cancel reason",
] as const

function exportRows(rows: ListRow[], stateLabel: (s: ListState) => string) {
  return rows.map((r) => [
    r.name,
    r.time,
    r.label,
    stateLabel(r.state),
    r.order_type || "",
    r.table_no || "",
    r.room_no || "",
    r.who || "",
    String(r.amount),
    String(r.items),
    String(r.voided),
    r.kot_no != null ? String(r.kot_no) : "",
    r.payment_mode || "",
    r.guests != null ? String(r.guests) : "",
    r.cancel_reason || "",
  ])
}

function downloadBlob(filename: string, mime: string, body: string) {
  const blob = new Blob([body], { type: mime })
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function escCsv(v: string) {
  return /[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

function escXml(v: string) {
  return v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function OrdersTab({ outlet, refreshKey, onOpenBill, onHistory }: {
  outlet: string; refreshKey: number; onOpenBill: (name: string) => void; onHistory?: () => void
}) {
  const { t } = useT()
  const label = useStateLabel()
  const today = localDay()
  const [from, setFrom] = useState(today)
  const [to, setTo] = useState(today)
  const [q, setQ] = useState("")
  const [qLive, setQLive] = useState("")
  const [only, setOnly] = useState<ListState | null>(null)
  const [data, setData] = useState<ListOut | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [viewing, setViewing] = useState<string | null>(null)

  useEffect(() => {
    const h = setTimeout(() => setQLive(q.trim()), 250)
    return () => clearTimeout(h)
  }, [q])

  const load = useCallback(() => {
    if (!outlet) return
    call<ListOut>("kamra.pos.orders_list", {
      outlet, date: from, to_date: to === from ? null : to, q: qLive || null, limit: 300,
    })
      .then((d) => { setData(d); setErr(null) })
      .catch((e) => setErr(serverError(e)))
  }, [outlet, from, to, qLive])
  useEffect(load, [load, refreshKey])


  if (viewing) {
    return <OrderView name={viewing} onBack={() => setViewing(null)}
      onOpenBill={(n) => onOpenBill(n)} />
  }
  const rows = (data?.rows ?? []).filter((r) => !only || r.state === only)
  const singleDay = from === to
  const isToday = singleDay && from === today
  const stamp = singleDay ? from : `${from}_to_${to}`

  function doExportCsv() {
    const lines = [
      EXPORT_COLS.join(","),
      ...exportRows(rows, label).map((cells) => cells.map(escCsv).join(",")),
    ]
    downloadBlob(`pos-orders-${stamp}.csv`, "text/csv;charset=utf-8", "\ufeff" + lines.join("\n") + "\n")
  }

  function doExportExcel() {
    const header = EXPORT_COLS.map((h) =>
      `<Cell><Data ss:Type="String">${escXml(h)}</Data></Cell>`).join("")
    const body = exportRows(rows, label).map((cells) =>
      `<Row>${cells.map((c) =>
        `<Cell><Data ss:Type="String">${escXml(c)}</Data></Cell>`).join("")}</Row>`).join("")
    const xml = `<?xml version="1.0"?><?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Orders"><Table>
<Row>${header}</Row>${body}
</Table></Worksheet></Workbook>`
    downloadBlob(`pos-orders-${stamp}.xls`, "application/vnd.ms-excel", xml)
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {onHistory && (
        <Button variant="outline" className="w-full" onClick={onHistory}>
          <History className="size-4" />{t("Full order history: any date, filters, export")}
        </Button>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <label className="relative min-w-[12rem] flex-1">
          <Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder={t("Bill, KOT, table, room, name or phone")}
            className="w-full rounded-lg border border-zinc-300 bg-white py-2 ps-8 pe-2 text-sm focus:outline-2 focus:outline-brand-600" />
        </label>
        <label className="text-xs text-zinc-500">
          <span className="mb-0.5 block font-medium">{t("From")}</span>
          <input type="date" value={from} max={to || today} aria-label={t("From")}
            onChange={(e) => setFrom(e.target.value || today)}
            className="w-[9.5rem] rounded-lg border border-zinc-300 bg-white px-2 py-2 text-sm" />
        </label>
        <label className="text-xs text-zinc-500">
          <span className="mb-0.5 block font-medium">{t("To")}</span>
          <input type="date" value={to} min={from} max={today} aria-label={t("To")}
            onChange={(e) => setTo(e.target.value || from)}
            className="w-[9.5rem] rounded-lg border border-zinc-300 bg-white px-2 py-2 text-sm" />
        </label>
        <div className="flex gap-1.5">
          <Button type="button" variant="outline" className="h-10 gap-1.5" disabled={rows.length === 0}
            onClick={doExportCsv} title={t("Download as CSV")}>
            <Download className="size-4" />{t("CSV")}
          </Button>
          <Button type="button" variant="outline" className="h-10 gap-1.5" disabled={rows.length === 0}
            onClick={doExportExcel} title={t("Download for Excel")}>
            <FileSpreadsheet className="size-4" />{t("Excel")}
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <button type="button" onClick={() => setOnly(null)}
          className={cn("rounded-full px-2.5 py-1 text-xs font-medium",
            only === null ? "bg-zinc-800 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
          {t("All")} · {data?.rows.length ?? 0}
        </button>
        {STATES.filter((s) => (data?.counts[s] ?? 0) > 0).map((s) => (
          <button type="button" key={s} onClick={() => setOnly(only === s ? null : s)}
            className={cn("rounded-full px-2.5 py-1 text-xs font-medium",
              only === s ? "bg-zinc-800 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
            {label(s)} · {data?.counts[s]}
          </button>
        ))}
        {rows.length > 0 && (
          <span className="ms-auto text-[11px] text-zinc-400">
            {t("Showing {n}", { n: rows.length })}
            {data && data.rows.length >= 300 ? ` · ${t("capped at 300")}` : ""}
          </span>
        )}
      </div>
      {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
      {data === null && !err ? (
        <p className="py-6 text-center text-sm text-zinc-400">{t("Loading…")}</p>
      ) : rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-zinc-400">
          {qLive ? t("No bills match.") : isToday ? t("No bills yet today.") : t("No bills in this range.")}
        </p>
      ) : (
        <>
          {/* compact cards on phone */}
          <ul className="space-y-1.5 md:hidden">
            {rows.map((r) => (
              <li key={r.name}>
                <button type="button"
                  onClick={() => (r.state === "open" || r.state === "sent") ? onOpenBill(r.name) : setViewing(r.name)}
                  className={cn("w-full rounded-2xl border bg-white px-3.5 py-2.5 text-start shadow-sm transition hover:border-brand-400",
                    r.stale ? "border-rose-300" : "border-zinc-200")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-[15px] font-semibold text-zinc-800">
                      {r.label}
                      {r.who && r.who !== r.label && <span className="ms-1 font-normal text-zinc-500">· {r.who}</span>}
                    </span>
                    <span className={cn("shrink-0 text-sm font-semibold tabular-nums",
                      r.state === "cancelled" && "text-zinc-400 line-through")}>
                      {cur()}{money(r.amount)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-500">
                    <StateBadge state={r.state} />
                    <span className="tabular-nums">{shortDay(dayOf(r.time))} {hhmm(r.time)}</span>
                    {r.kot_no ? <span>· {t("KOT {n}", { n: r.kot_no })}</span> : null}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          {/* wide table on tablet+ */}
          <div className="hidden min-h-0 flex-1 overflow-auto rounded-xl border border-zinc-200 bg-white md:block">
            <table className="w-full min-w-[52rem] border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-zinc-50 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
                <tr className="border-b border-zinc-200">
                  <th className="px-3 py-2.5">{t("Time")}</th>
                  <th className="px-3 py-2.5">{t("Bill")}</th>
                  <th className="px-3 py-2.5">{t("State")}</th>
                  <th className="px-3 py-2.5">{t("Type")}</th>
                  <th className="px-3 py-2.5">{t("Where")}</th>
                  <th className="px-3 py-2.5">{t("Customer")}</th>
                  <th className="px-3 py-2.5 text-end">{t("Amount")}</th>
                  <th className="px-3 py-2.5 text-end">{t("Items")}</th>
                  <th className="px-3 py-2.5">{t("Pay")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.name}
                    onClick={() => (r.state === "open" || r.state === "sent") ? onOpenBill(r.name) : setViewing(r.name)}
                    className={cn(
                      "cursor-pointer border-b border-zinc-100 transition hover:bg-brand-50/60",
                      !!r.stale && "bg-rose-50/40",
                    )}>
                    <td className="whitespace-nowrap px-3 py-2.5 tabular-nums text-zinc-600">
                      {shortDay(dayOf(r.time))} {hhmm(r.time)}
                      {!!r.carried && <span className="ms-1 text-[10px] font-semibold text-rose-600">{t("carried")}</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-semibold text-zinc-800">{r.label}</div>
                      <div className="text-[11px] text-zinc-400">
                        {r.name}{r.kot_no ? ` · KOT ${r.kot_no}` : ""}
                      </div>
                    </td>
                    <td className="px-3 py-2.5"><StateBadge state={r.state} /></td>
                    <td className="px-3 py-2.5 text-zinc-600">{r.order_type || "-"}</td>
                    <td className="px-3 py-2.5 text-zinc-600">
                      {r.table_no ? t("Table {n}", { n: r.table_no })
                        : r.room_no ? t("Room {n}", { n: r.room_no }) : "-"}
                    </td>
                    <td className="max-w-[10rem] truncate px-3 py-2.5 text-zinc-600">{r.who || "-"}</td>
                    <td className={cn("px-3 py-2.5 text-end font-semibold tabular-nums",
                      r.state === "cancelled" && "text-zinc-400 line-through")}>
                      {cur()}{money(r.amount)}
                    </td>
                    <td className="px-3 py-2.5 text-end tabular-nums text-zinc-600">
                      {r.items}{r.voided > 0 ? <span className="text-rose-600"> (−{r.voided})</span> : null}
                    </td>
                    <td className="px-3 py-2.5 text-zinc-600">{r.payment_mode || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export function OrderView({ name, onBack, onOpenBill }: {
  name: string; onBack: () => void; onOpenBill: (n: string) => void
}) {
  const { t } = useT()
  const [d, setD] = useState<ViewDetail | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    call<ViewDetail>("kamra.pos.order_detail", { order: name })
      .then(setD).catch((e) => setErr(serverError(e)))
  }, [name])
  const [changing, setChanging] = useState(false)
  const [busy, setBusy] = useState(false)
  async function changeMode(mode: string) {
    setBusy(true)
    try {
      await call("kamra.pos.change_payment_mode", { order: name, mode, reason: "" })
      setD(await call<ViewDetail>("kamra.pos.order_detail", { order: name }))
      setChanging(false); setErr(null)
    } catch (e) { setErr(serverError(e)) } finally { setBusy(false) }
  }
  async function printBill() {
    try {
      const bill = await call<BillData>("kamra.pos.bill_data", { order: name })
      printThermal(`Bill ${name}`, billHtml(bill))
    } catch (e) { setErr(serverError(e)) }
  }
  return (
    <div className="space-y-3">
      <button onClick={onBack} className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <ArrowLeft className="size-4 rtl:rotate-180" />{t("All orders")}
      </button>
      {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
      {!d ? (!err && <p className="py-6 text-center text-sm text-zinc-400">{t("Loading…")}</p>) : (
        <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-zinc-800">
                {d.table_no ? t("Table {n}", { n: d.table_no })
                  : d.room ? t("Room {n}", { n: d.room.split("-").pop() || "" }) : (d.order_type || d.name)}
              </h3>
              <p className="text-xs text-zinc-500">
                {d.name} · {shortDay(dayOf(d.creation))} {hhmm(d.creation)}
                {d.kot_no ? ` · ${t("KOT {n}", { n: d.kot_no })}` : ""}
                {d.customer_name ? ` · ${d.customer_name}` : ""}
              </p>
            </div>
            <StateBadge state={d.state} />
          </div>
          <ul className="divide-y divide-zinc-100 text-sm">
            {d.items.map((it) => (
              <li key={it.row} className="py-1.5">
                <div className={cn("flex justify-between gap-2", !!it.voided && "text-zinc-400 line-through")}>
                  <span>{Math.round(it.qty)}× {it.item_name}</span>
                  <span className="tabular-nums">{cur()}{money(it.voided ? 0 : it.amount)}</span>
                </div>
                {!!it.voided && (
                  <p className="text-[11px] text-rose-700">
                    {it.kot_status !== "New" ? t("Voided after the kitchen had it") : t("Voided")}
                    {it.void_reason ? `: ${it.void_reason}` : ""}
                    {it.void_approved_by ? ` · ${t("approved by {name}", { name: it.void_approved_by })}` : ""}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <div className="space-y-0.5 border-t border-zinc-100 pt-2 text-sm">
            {d.discount_amount > 0 && (
              <div className="flex justify-between text-zinc-500"><span>{t("Discount")}</span><span className="tabular-nums">-{cur()}{money(d.discount_amount)}</span></div>
            )}
            <div className="flex justify-between font-semibold"><span>{t("Total before tax")}</span><span className="tabular-nums">{cur()}{money(d.order_total)}</span></div>
            {d.state === "paid" && (
              <div className="space-y-1.5">
                <p className="text-xs text-emerald-700">{t("Paid by {mode}", { mode: d.payment_mode || "" })}</p>
                {changing ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-zinc-500">{t("It was paid by")}</span>
                    {["Cash", "Card", "UPI"].filter((m) => m !== d.payment_mode).map((m) => (
                      <Button key={m} variant="outline" className="h-9" disabled={busy} onClick={() => changeMode(m)}>{m}</Button>
                    ))}
                    <Button variant="ghost" className="h-9" onClick={() => setChanging(false)}>{t("Back")}</Button>
                  </div>
                ) : (
                  <button className="text-xs font-semibold text-brand-700 hover:underline" onClick={() => setChanging(true)}>
                    {t("Wrong payment mode? Change it")}
                  </button>
                )}
              </div>
            )}
            {d.state === "room" && <p className="text-xs text-violet-700">{t("Posted to the room folio")}</p>}
            {d.state === "nc" && <p className="text-xs text-amber-700">{t("Complimentary, authorized by {who}", { who: d.nc_authorized_by || "" })}</p>}
          </div>
          {d.state === "cancelled" && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">
              <p className="font-semibold">{t("Cancelled")}{d.cancelled_at ? ` · ${hhmm(d.cancelled_at)}` : ""}</p>
              {d.cancel_reason && <p>{d.cancel_reason}</p>}
              {d.cancelled_by && <p>{t("by {name}", { name: d.cancelled_by })}{d.cancel_approved_by ? ` · ${t("approved by {name}", { name: d.cancel_approved_by })}` : ""}</p>}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {(d.state === "open" || d.state === "sent") && (
              <Button className="h-10" onClick={() => onOpenBill(d.name)}>{t("Open on the till")}</Button>
            )}
            {d.state !== "cancelled" && (
              <Button variant="outline" className="h-10" onClick={printBill}>
                <Receipt className="size-4" />{d.state === "open" || d.state === "sent" ? t("Print bill") : t("Reprint bill")}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── guest ──────────────────────────────────────────────────────────── */

function GuestTab({ outlet, order, draft, refreshKey, onDraftGuest, onChanged }: {
  outlet: string
  order: string | null
  draft: { room: string | null; guest: string | null }
  refreshKey: number
  onDraftGuest: (g: { guest: string; full_name: string } | null) => void
  onChanged: () => void
}) {
  const { t } = useT()
  const [data, setData] = useState<GuestPanelData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!outlet) return
    if (!order && !draft.room && !draft.guest) { setData({ kind: "none" }); return }
    call<GuestPanelData>("kamra.pos.guest_panel", order
      ? { outlet, order }
      : { outlet, guest: draft.guest, room: draft.room })
      .then((d) => { setData(d); setErr(null) })
      .catch((e) => setErr(serverError(e)))
  }, [outlet, order, draft.room, draft.guest])
  useEffect(load, [load, refreshKey])

  async function attach(args: { guest?: string; customer_name?: string; phone?: string }) {
    setBusy(true); setErr(null)
    try {
      const r = await call<{ guest: string; full_name: string }>("kamra.pos.attach_customer",
        { outlet, order, ...args })
      if (!order) onDraftGuest({ guest: r.guest, full_name: r.full_name })
      else { onChanged(); load() }
    } catch (e) { setErr(serverError(e)) }
    finally { setBusy(false) }
  }
  async function detach() {
    if (!order) { onDraftGuest(null); return }
    setBusy(true); setErr(null)
    try {
      await call("kamra.pos.attach_customer", { outlet, order, clear: 1 })
      onChanged(); load()
    } catch (e) { setErr(serverError(e)) }
    finally { setBusy(false) }
  }

  if (!data) return <p className="py-6 text-center text-sm text-zinc-400">{err || t("Loading…")}</p>
  const g = data.guest
  return (
    <div className="space-y-3">
      {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}

      {data.kind === "in_house" && data.stay && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-3">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-700">
            <BedDouble className="size-3.5" />{t("In-house guest")}
          </p>
          <p className="mt-1 flex items-center gap-1.5 text-base font-semibold text-violet-950">
            {g?.full_name || data.stay.guest_name}
            {!!g?.vip && <Star className="size-4 fill-amber-400 text-amber-500" aria-label={t("VIP")} />}
          </p>
          <p className="text-sm text-violet-900">
            {t("Room {n}", { n: data.stay.room_number || "" })} · {shortDay(data.stay.check_in_date)} {t("to")} {shortDay(data.stay.check_out_date)}
          </p>
          <p className={cn("mt-2 rounded-lg px-2 py-1.5 text-xs font-medium",
            data.stay.room_charges_allowed ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800")}>
            {data.stay.room_charges_allowed
              ? t("Room charges allowed: this bill can be posted to the room.")
              : t("Room charges blocked at check-in. Take payment at the outlet.")}
          </p>
        </div>
      )}

      {data.kind === "customer" && g && (
        <div className="rounded-xl border border-zinc-200 bg-white p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{t("Customer")}</p>
              <p className="mt-0.5 flex items-center gap-1.5 text-base font-semibold text-zinc-800">
                {g.full_name}
                {!!g.vip && <Star className="size-4 fill-amber-400 text-amber-500" aria-label={t("VIP")} />}
              </p>
              {g.phone && <p className="flex items-center gap-1 text-sm text-zinc-500"><Phone className="size-3.5" />{g.phone}</p>}
            </div>
            <Button variant="ghost" className="!px-2 text-xs text-rose-600" disabled={busy} onClick={detach}>
              {t("Remove from bill")}
            </Button>
          </div>
        </div>
      )}

      {(g?.notes || data.allergy_note) && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">{t("Notes: preferences and allergies")}</p>
          {data.allergy_note && <p className="mt-1 font-semibold">{t("This bill")}: {data.allergy_note}</p>}
          {g?.notes && <p className="mt-1 whitespace-pre-line">{g.notes}</p>}
        </div>
      )}

      {data.history && data.kind !== "none" && (
        <div className="rounded-xl border border-zinc-200 bg-white p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{t("At this outlet before")}</p>
          {data.history.bills === 0 ? (
            <p className="mt-1 text-sm text-zinc-500">{t("First visit here.")}</p>
          ) : (
            <>
              <p className="mt-1 text-sm text-zinc-700">
                {t("Visits: {visits} · Bills: {bills} · Spent: {amount} · Last: {day}", {
                  visits: data.history.visits, bills: data.history.bills,
                  amount: `${cur()}${money(data.history.spend)}`,
                  day: shortDay(data.history.last_visit || ""),
                })}
              </p>
              <ul className="mt-2 space-y-1.5">
                {data.history.orders.map((o) => (
                  <li key={o.name} className="rounded-lg bg-zinc-50 px-2 py-1.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-700">{shortDay(dayOf(o.time))} · {o.label}</span>
                      <span className="flex items-center gap-1.5">
                        <StateBadge state={o.state} />
                        <span className="font-semibold tabular-nums">{cur()}{money(o.amount)}</span>
                      </span>
                    </div>
                    {o.items && <p className="mt-0.5 truncate text-zinc-500">{o.items}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {data.kind !== "in_house" && (
        <CustomerFinder outlet={outlet} busy={busy} replacing={data.kind === "customer"}
          onPick={(guest) => attach({ guest })}
          onCreate={(customer_name, phone) => attach({ customer_name, phone })} />
      )}
    </div>
  )
}

function CustomerFinder({ outlet, busy, replacing, onPick, onCreate }: {
  outlet: string
  busy: boolean
  replacing: boolean
  onPick: (guest: string) => void
  onCreate: (name: string, phone: string) => void
}) {
  const { t } = useT()
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<CustomerHit[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState("")
  const [phone, setPhone] = useState("")
  const seq = useRef(0)
  useEffect(() => {
    const s = q.trim()
    const digits = s.replace(/\D/g, "")
    if (s.length < 3 && digits.length < 4) { setHits(null); return }
    const n = ++seq.current
    const h = setTimeout(() => {
      call<CustomerHit[]>("kamra.pos.find_customer", { outlet, q: s })
        .then((r) => { if (n === seq.current) setHits(r) })
        .catch(() => { if (n === seq.current) setHits([]) })
    }, 250)
    return () => clearTimeout(h)
  }, [q, outlet])
  function startAdd() {
    const s = q.trim()
    const digits = s.replace(/\D/g, "")
    // carry what was typed into the right box
    if (digits.length >= 4 && digits.length >= s.replace(/\s/g, "").length - 1) setPhone(s)
    else setName(s)
    setAdding(true)
  }
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
        {replacing ? t("A different customer") : t("Who is this bill for?")}
      </p>
      {!adding ? (
        <>
          <label className="relative block">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} inputMode="search"
              placeholder={t("Phone or name")}
              className="w-full rounded-lg border border-zinc-300 py-2 ps-8 pe-2 text-sm focus:outline-2 focus:outline-brand-600" />
          </label>
          {hits && (
            <ul className="mt-2 space-y-1">
              {hits.map((h) => (
                <li key={h.guest}>
                  <button disabled={busy} onClick={() => onPick(h.guest)}
                    className="flex w-full items-center justify-between gap-2 rounded-lg border border-zinc-200 px-2.5 py-2 text-start text-sm hover:border-brand-400">
                    <span className="min-w-0">
                      <span className="flex items-center gap-1 font-medium text-zinc-800">
                        {h.full_name}{!!h.vip && <Star className="size-3.5 fill-amber-400 text-amber-500" />}
                      </span>
                      <span className="block text-xs text-zinc-500">
                        {h.phone || ""}{h.in_house_room ? ` · ${t("in house, room {n}", { n: h.in_house_room })}` : ""}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs text-zinc-500">{t("Bills here: {n}", { n: h.visits })}</span>
                  </button>
                </li>
              ))}
              {hits.length === 0 && <li className="py-1 text-xs text-zinc-500">{t("No guest found.")}</li>}
            </ul>
          )}
          <Button variant="outline" className="mt-2 h-10 w-full" onClick={startAdd}>
            <UserPlus className="size-4" />{t("Add a new customer")}
          </Button>
        </>
      ) : (
        <div className="space-y-2">
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Name")}
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-2 focus:outline-brand-600" />
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={t("Phone")} inputMode="tel"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-2 focus:outline-brand-600" />
          <p className="text-[11px] text-zinc-500">{t("Only a name and phone are kept. A phone already on file reuses that guest.")}</p>
          <div className="flex gap-2">
            <Button className="h-10 flex-1" disabled={busy || (!name.trim() && !phone.trim())}
              onClick={() => onCreate(name.trim(), phone.trim())}>
              {t("Save and attach")}
            </Button>
            <Button variant="ghost" className="h-10" onClick={() => setAdding(false)}>{t("Back")}</Button>
          </div>
        </div>
      )}
    </div>
  )
}
