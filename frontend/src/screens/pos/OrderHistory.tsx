/*  Order history: every bill the outlet has ever taken, on one wide screen.
    Date presets (today to a whole year), type, payment mode and state
    filters, a search that reaches bills, KOTs, tables, rooms, names and
    phones, totals over everything the filters match (not only the page on
    screen), paging, and a CSV export of exactly what is filtered. Rows
    carry plain, labelled buttons rather than a hidden menu. From
    kamra.pos (orders_list, orders_export); a bill opens in the same
    OrderView the side panel uses, so reprint and "wrong payment mode"
    work from here too. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Download, Receipt, Search, X } from "lucide-react"
import { call } from "../../lib/api"
import { serverError } from "../../lib/resource"
import { cur } from "../../lib/money"
import { useT } from "../../lib/i18n"
import { cn } from "../../lib/utils"
import { Button } from "../../components/ui/button"
import {
  OrderView, STATES, StateBadge, hhmm, localDay, money, shortDay, useStateLabel,
  type ListState,
} from "./PosSidePanel"

interface Row {
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
  time: string
  stale: 0 | 1
  carried: 0 | 1
  cancel_reason: string | null
}
interface Out {
  rows: Row[]
  counts: Record<ListState, number>
  total: number
  has_more: boolean
  truncated: boolean
  totals: {
    bills: number
    sales: number
    cancelled: number
    by_mode: Record<string, number>
    by_type: Record<string, number>
  }
}

const PAGE = 100
const ORDER_TYPES = ["Dine In", "Room Service", "Takeaway", "Delivery"]
const MODES = ["Cash", "Card", "UPI", "Room"]

type Preset = "today" | "yesterday" | "week" | "month30" | "thismonth" | "year" | "custom"

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return localDay(d)
}
function range(p: Exclude<Preset, "custom">): [string, string] {
  const today = localDay()
  switch (p) {
    case "today": return [today, today]
    case "yesterday": return [daysAgo(1), daysAgo(1)]
    case "week": return [daysAgo(6), today]
    case "month30": return [daysAgo(29), today]
    case "thismonth": return [today.slice(0, 8) + "01", today]
    case "year": return [daysAgo(365), today]
  }
}

const selectCls =
  "rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-sm text-zinc-700 focus:outline-2 focus:outline-brand-600"

export default function OrderHistory({ outlet, onClose, onOpenBill }: {
  outlet: string
  onClose: () => void
  onOpenBill: (name: string) => void
}) {
  const { t } = useT()
  const label = useStateLabel()
  const [preset, setPreset] = useState<Preset>("today")
  const [[from, to], setSpan] = useState<[string, string]>(range("today"))
  const [q, setQ] = useState("")
  const [qLive, setQLive] = useState("")
  const [only, setOnly] = useState<ListState | null>(null)
  const [orderType, setOrderType] = useState("")
  const [mode, setMode] = useState("")
  const [data, setData] = useState<Out | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [viewing, setViewing] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const h = setTimeout(() => setQLive(q.trim()), 250)
    return () => clearTimeout(h)
  }, [q])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !viewing) onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose, viewing])

  const args = useMemo(() => ({
    outlet, date: from, to_date: to, q: qLive || null, state: only,
    order_type: orderType || null, mode: mode || null,
  }), [outlet, from, to, qLive, only, orderType, mode])

  const load = useCallback((offset: number) => {
    setLoading(true)
    call<Out>("kamra.pos.orders_list", { ...args, limit: PAGE, offset })
      .then((d) => {
        setData(d)
        setRows((prev) => (offset === 0 ? d.rows : [...prev, ...d.rows]))
        setErr(null)
      })
      .catch((e) => setErr(serverError(e)))
      .finally(() => setLoading(false))
  }, [args])
  useEffect(() => { load(0) }, [load])

  function pick(p: Preset) {
    setPreset(p)
    if (p !== "custom") setSpan(range(p))
  }

  async function exportCsv() {
    setExporting(true)
    try {
      const out = await call<{ filename: string; csv: string }>("kamra.pos.orders_export", {
        outlet, date: from, to_date: to, q: qLive || null, state: only,
        mode: mode || null, order_type: orderType || null,
      })
      const url = URL.createObjectURL(new Blob([out.csv], { type: "text/csv;charset=utf-8" }))
      const a = document.createElement("a")
      a.href = url; a.download = out.filename
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
      setErr(null)
    } catch (e) { setErr(serverError(e)) } finally { setExporting(false) }
  }

  function open(r: Row) {
    if (r.state === "open" || r.state === "sent") onOpenBill(r.name)
    else setViewing(r.name)
  }

  const presets: [Preset, string][] = [
    ["today", t("Today")], ["yesterday", t("Yesterday")], ["week", t("Last 7 days")],
    ["month30", t("Last 30 days")], ["thismonth", t("This month")], ["year", t("Last year")],
    ["custom", t("Pick dates")],
  ]
  const totals = data?.totals
  const span = from === to ? shortDay(from) : `${shortDay(from)} - ${shortDay(to)}`

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-zinc-50" role="dialog" aria-label={t("Order history")}>
      <header className="flex shrink-0 flex-wrap items-center gap-2 border-b border-zinc-200 bg-white px-4 py-3">
        <Receipt className="size-5 text-brand-700" aria-hidden />
        <div className="me-auto min-w-0">
          <h1 className="text-lg font-semibold text-zinc-900">{t("Order history")}</h1>
          <p className="text-xs text-zinc-500">{outlet} · {span}</p>
        </div>
        <Button variant="outline" disabled={exporting || !data} onClick={exportCsv}
          title={t("Download exactly these bills as a spreadsheet (CSV)")}>
          <Download className="size-4" />{exporting ? t("Preparing…") : t("Export CSV")}
        </Button>
        <Button variant="outline" onClick={onClose}><X className="size-4" />{t("Close")}</Button>
      </header>

      {viewing ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-2xl p-4">
            <OrderView name={viewing} onBack={() => { setViewing(null); load(0) }}
              onOpenBill={(n) => { setViewing(null); onOpenBill(n) }} />
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl space-y-3 p-4">
            {/* when */}
            <div className="flex flex-wrap items-center gap-1.5">
              {presets.map(([p, text]) => (
                <button key={p} onClick={() => pick(p)} aria-pressed={preset === p}
                  className={cn("rounded-full px-3 py-1.5 text-sm font-medium",
                    preset === p ? "bg-brand-600 text-white" : "bg-white text-zinc-700 ring-1 ring-zinc-200 hover:bg-zinc-100")}>
                  {text}
                </button>
              ))}
              {preset === "custom" && (
                <span className="flex items-center gap-1.5">
                  <input type="date" value={from} max={localDay()} aria-label={t("From")}
                    onChange={(e) => setSpan([e.target.value || localDay(), to < e.target.value ? e.target.value : to])}
                    className={selectCls} />
                  <span className="text-zinc-400">-</span>
                  <input type="date" value={to} min={from} max={localDay()} aria-label={t("To")}
                    onChange={(e) => setSpan([from, e.target.value || localDay()])}
                    className={selectCls} />
                </span>
              )}
            </div>

            {/* what */}
            <div className="flex flex-wrap items-center gap-2">
              <label className="relative min-w-[14rem] flex-1">
                <Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
                <input value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder={t("Bill, KOT, table, room, name or phone")}
                  className="w-full rounded-lg border border-zinc-300 bg-white py-2 ps-8 pe-2 text-sm focus:outline-2 focus:outline-brand-600" />
              </label>
              <select value={orderType} onChange={(e) => setOrderType(e.target.value)}
                aria-label={t("Order type")} className={selectCls}>
                <option value="">{t("All order types")}</option>
                {ORDER_TYPES.map((o) => <option key={o} value={o}>{t(o)}</option>)}
              </select>
              <select value={mode} onChange={(e) => setMode(e.target.value)}
                aria-label={t("Payment mode")} className={selectCls}>
                <option value="">{t("All payment modes")}</option>
                {MODES.map((m) => <option key={m} value={m}>{m === "Room" ? t("Posted to room") : m}</option>)}
              </select>
            </div>

            <div className="flex flex-wrap gap-1.5">
              <button onClick={() => setOnly(null)} aria-pressed={only === null}
                className={cn("rounded-full px-3 py-1 text-xs font-medium",
                  only === null ? "bg-zinc-800 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
                {t("All")} · {data ? Object.values(data.counts).reduce((a, b) => a + b, 0) : 0}
              </button>
              {STATES.filter((s) => (data?.counts[s] ?? 0) > 0).map((s) => (
                <button key={s} onClick={() => setOnly(only === s ? null : s)} aria-pressed={only === s}
                  className={cn("rounded-full px-3 py-1 text-xs font-medium",
                    only === s ? "bg-zinc-800 text-white" : "bg-white text-zinc-600 ring-1 ring-zinc-200")}>
                  {label(s)} · {data?.counts[s]}
                </button>
              ))}
            </div>

            {/* totals over everything the filters match */}
            {totals && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                <Tile title={t("Bills")} value={String(totals.bills)} />
                <Tile title={t("Sales")} value={`${cur()}${money(totals.sales)}`} strong />
                {Object.entries(totals.by_mode).map(([m, v]) => (
                  <Tile key={m} title={m === "Room" ? t("Posted to room") : m} value={`${cur()}${money(v)}`} />
                ))}
                {totals.cancelled > 0 && (
                  <Tile title={t("Cancelled")} value={`${cur()}${money(totals.cancelled)}`} tone="rose" />
                )}
              </div>
            )}

            {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
            {data?.truncated && (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {t("Too many bills in this range to list them all. Narrow the dates, or export the range.")}
              </p>
            )}

            {data === null && !err ? (
              <p className="py-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>
            ) : rows.length === 0 && !loading ? (
              <p className="rounded-xl border border-dashed border-zinc-300 bg-white py-10 text-center text-sm text-zinc-500">
                {t("No bills match these filters.")}
              </p>
            ) : (
              <>
                {/* wide screens: a table */}
                <div className="hidden overflow-x-auto rounded-xl border border-zinc-200 bg-white md:block">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-3 py-2 text-start font-medium">{t("Bill")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Date")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Type")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Table or room")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Guest or customer")}</th>
                        <th className="px-3 py-2 text-end font-medium">{t("Items")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Paid by")}</th>
                        <th className="px-3 py-2 text-start font-medium">{t("Status")}</th>
                        <th className="px-3 py-2 text-end font-medium">{t("Amount")}</th>
                        <th className="px-3 py-2"><span className="sr-only">{t("Actions")}</span></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {rows.map((r) => (
                        <tr key={r.name} onClick={() => open(r)}
                          className={cn("cursor-pointer hover:bg-brand-50/40", r.stale ? "bg-rose-50/50" : "")}>
                          <td className="px-3 py-2 font-medium text-zinc-900">
                            {r.name}{r.kot_no ? <span className="ms-1 text-xs font-normal text-zinc-500">KOT {r.kot_no}</span> : null}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 tabular-nums text-zinc-600">
                            {shortDay(r.time.slice(0, 10))} {hhmm(r.time)}
                            {r.carried ? <span className="ms-1 text-xs text-rose-600">{t("carried over")}</span> : null}
                          </td>
                          <td className="px-3 py-2 text-zinc-600">{r.order_type ? t(r.order_type) : ""}</td>
                          <td className="px-3 py-2 text-zinc-600">{r.room_no ? `${t("Room")} ${r.room_no}` : r.table_no ?? ""}</td>
                          <td className="max-w-[12rem] truncate px-3 py-2 text-zinc-700">{r.who ?? ""}</td>
                          <td className="px-3 py-2 text-end tabular-nums text-zinc-600">{r.items}</td>
                          <td className="px-3 py-2 text-zinc-600">{r.state === "room" ? t("Posted to room") : r.state === "paid" ? r.payment_mode ?? "" : ""}</td>
                          <td className="px-3 py-2">
                            <StateBadge state={r.state} />
                            {r.state === "cancelled" && r.cancel_reason
                              ? <span className="ms-1.5 text-xs text-rose-700">{r.cancel_reason}</span> : null}
                          </td>
                          <td className={cn("px-3 py-2 text-end font-semibold tabular-nums",
                            r.state === "cancelled" && "text-zinc-400 line-through")}>
                            {cur()}{money(r.amount)}
                          </td>
                          <td className="px-3 py-2 text-end">
                            <Button variant={r.state === "open" || r.state === "sent" ? "primary" : "outline"}
                              className="h-8 px-3 text-xs"
                              onClick={(e) => { e.stopPropagation(); open(r) }}>
                              {r.state === "open" || r.state === "sent" ? t("Open on till") : t("View bill")}
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* phones: cards */}
                <ul className="space-y-2 md:hidden">
                  {rows.map((r) => (
                    <li key={r.name}>
                      <button onClick={() => open(r)}
                        className={cn("w-full rounded-xl border bg-white p-3 text-start",
                          r.stale ? "border-rose-300" : "border-zinc-200")}>
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold text-zinc-900">
                            {r.label}{r.who && r.who !== r.label ? <span className="font-normal text-zinc-500"> · {r.who}</span> : null}
                          </span>
                          <span className={cn("shrink-0 text-sm font-semibold tabular-nums",
                            r.state === "cancelled" && "text-zinc-400 line-through")}>
                            {cur()}{money(r.amount)}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
                          <StateBadge state={r.state} />
                          <span>{shortDay(r.time.slice(0, 10))} {hhmm(r.time)}</span>
                          <span>· {r.name}</span>
                          {r.order_type ? <span>· {t(r.order_type)}</span> : null}
                          {r.state === "paid" && r.payment_mode ? <span>· {r.payment_mode}</span> : null}
                          {r.state === "room" ? <span>· {t("Posted to room")}</span> : null}
                        </div>
                        <span className="mt-2 inline-block rounded-lg border border-zinc-300 px-3 py-1 text-xs font-semibold text-zinc-700">
                          {r.state === "open" || r.state === "sent" ? t("Open on till") : t("View bill")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>

                <div className="flex flex-col items-center gap-1 pb-6 pt-2">
                  <p className="text-xs text-zinc-500">
                    {t("Showing {n} of {total} bills", { n: rows.length, total: data?.total ?? rows.length })}
                  </p>
                  {data?.has_more && (
                    <Button variant="outline" disabled={loading} onClick={() => load(rows.length)}>
                      {loading ? t("Loading…") : t("Show more bills")}
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Tile({ title, value, strong, tone }: {
  title: string; value: string; strong?: boolean; tone?: "rose"
}) {
  return (
    <div className={cn("rounded-xl border bg-white px-3 py-2",
      tone === "rose" ? "border-rose-200" : "border-zinc-200")}>
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">{title}</p>
      <p className={cn("tabular-nums", strong ? "text-lg font-semibold text-zinc-900" : "text-base font-medium text-zinc-800",
        tone === "rose" && "text-rose-700")}>{value}</p>
    </div>
  )
}
