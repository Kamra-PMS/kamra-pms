/*  Kitchen stock over a period: what each ingredient started with, what came
    in and went out by kind, and what was left (kamra.inventory.stock_summary).
    One row per ingredient per outlet - never a merged total. */

import { useEffect, useState } from "react"
import { Download } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { downloadCsv } from "../lib/csv"
import { periodRange, type Period } from "../lib/periods"
import { useT, t as translate } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "../components/ui/button"

export interface SummaryRow {
  ingredient: string
  ingredient_name: string
  category: string | null
  uom: string
  outlet: string
  outlet_name: string
  beginning: number
  purchases: number
  production: number
  used: number
  wastage: number
  adjustment: number
  ending: number
  low: boolean
}

/** The movement columns, in the order they are shown and exported. */
const COLUMNS = ["beginning", "purchases", "production", "used", "wastage", "adjustment", "ending"] as const

const fmt = (n: number) => (Math.round(n * 1000) / 1000).toString()
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
const box = "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"

export default function StockSummary({ outlets, outlet, onOpen }: {
  outlets: { name: string; outlet_name: string }[]
  outlet: string
  onOpen: (row: SummaryRow, from: string, to: string) => void
}) {
  const { t } = useT()
  const [period, setPeriod] = useState<Period | "custom">("thisMonth")
  const [custom, setCustom] = useState<[string, string]>(() => periodRange("thisMonth", today()))
  const [where, setWhere] = useState(outlet)
  const [search, setSearch] = useState("")
  const [lowOnly, setLowOnly] = useState(false)
  const [rows, setRows] = useState<SummaryRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [from, to] = period === "custom" ? custom : periodRange(period, today())

  useEffect(() => {
    let live = true
    const wait = setTimeout(() => {
      call<{ rows: SummaryRow[] }>("kamra.inventory.stock_summary", {
        property: getCurrentProperty(), from_date: from, to_date: to,
        outlet: where || null, search: search.trim() || null, low_only: lowOnly ? 1 : 0,
      }).then((r) => { if (live) { setRows(r.rows); setError(null) } })
        .catch((e) => { if (live) setError(serverError(e)) })
    }, 250)
    return () => { live = false; clearTimeout(wait) }
  }, [from, to, where, search, lowOnly])

  const head: Record<(typeof COLUMNS)[number], string> = {
    beginning: t("Beginning"), purchases: t("Purchases"), production: t("Production"), used: t("Used"),
    wastage: t("Wastage"), adjustment: t("Adjustment"), ending: t("Ending"),
  }
  const all = !where
  const exportCsv = () => downloadCsv(
    `stock-${from}_${to}`,
    [t("Ingredient"), t("Category"), ...(all ? [t("Outlet")] : []), ...COLUMNS.map((c) => head[c]), t("Unit")],
    (rows ?? []).map((r) => [r.ingredient_name, r.category ?? "", ...(all ? [r.outlet_name] : []),
      ...COLUMNS.map((c) => r[c]), r.uom]),
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select className={box} value={period} aria-label={t("Period")}
          onChange={(e) => {
            const next = e.target.value as Period | "custom"
            if (next === "custom") setCustom([from, to])
            setPeriod(next)
          }}>
          <option value="today">{t("Today")}</option>
          <option value="yesterday">{t("Yesterday")}</option>
          <option value="thisWeek">{t("This week")}</option>
          <option value="lastWeek">{t("Last week")}</option>
          <option value="thisMonth">{t("This month")}</option>
          <option value="lastMonth">{t("Last month")}</option>
          <option value="custom">{t("Custom")}</option>
        </select>
        {period === "custom" && (
          <>
            <input type="date" className={box} value={custom[0]} aria-label={t("From")}
              onChange={(e) => e.target.value && setCustom([e.target.value, custom[1]])} />
            <input type="date" className={box} value={custom[1]} aria-label={t("To")}
              onChange={(e) => e.target.value && setCustom([custom[0], e.target.value])} />
          </>
        )}
        <select className={box} value={where} onChange={(e) => setWhere(e.target.value)} aria-label={t("Outlet")}>
          <option value="">{t("All outlets")}</option>
          {outlets.map((o) => <option key={o.name} value={o.name}>{o.outlet_name}</option>)}
        </select>
        <input className={box} value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder={t("Search…")} aria-label={t("Search…")} />
        <label className="flex items-center gap-1.5 text-sm text-zinc-600">
          <input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} />{t("Low only")}
        </label>
        <Button variant="outline" className="ms-auto" disabled={!rows?.length} onClick={exportCsv}>
          <Download className="size-4" />{t("Export CSV")}</Button>
      </div>
      {error && <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-700">{translate(error)}</div>}
      {rows === null ? (
        !error && <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 p-12 text-center text-zinc-400">
          {t("No stock or movements in this period.")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-3 py-2">{t("Ingredient")}</th>
                <th className="px-3 py-2">{t("Category")}</th>
                {all && <th className="px-3 py-2">{t("Outlet")}</th>}
                {COLUMNS.map((c) => <th key={c} className="px-3 py-2 text-end">{head[c]}</th>)}
                <th className="px-3 py-2">{t("Unit")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((r) => (
                <tr key={`${r.outlet}:${r.ingredient}`} onClick={() => onOpen(r, from, to)}
                  className={cn("cursor-pointer hover:bg-brand-50/40", r.low && "bg-amber-50/60")}>
                  <td className="px-3 py-2 font-semibold text-zinc-800">
                    <button type="button" className="text-start">{r.ingredient_name}</button>
                  </td>
                  <td className="px-3 py-2 text-zinc-500">{translate(r.category) || "-"}</td>
                  {all && <td className="px-3 py-2 text-zinc-500">{r.outlet_name}</td>}
                  {COLUMNS.map((c) => (
                    <td key={c} className={cn("px-3 py-2 text-end tabular-nums",
                      c === "ending" ? "font-bold text-zinc-900" : r[c] === 0 ? "text-zinc-300" : "text-zinc-700",
                      r[c] < 0 && c !== "used" && c !== "wastage" && c !== "production" && "text-rose-600")}>
                      {fmt(r[c])}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-zinc-400">{r.uom}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
