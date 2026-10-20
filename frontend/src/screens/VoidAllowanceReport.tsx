/*  Voids & allowances: every void, allowance and cancelled invoice on the
    property in a date window - who reversed what, when and why. Read
    straight from the action log by kamra.reports.void_allowance_report, so
    it cannot drift from what actually happened. Finance / Hotel Admin. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Printer, Search } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { useT } from "../lib/i18n"

interface Row {
  when: string
  actor: string
  action: string
  folio: string | null
  detail: string | null
}

const ACTIONS = ["Void", "Allowance", "Invoice cancelled"] as const

const iso = (d: Date) => d.toISOString().slice(0, 10)

export default function VoidAllowanceReport() {
  const { t } = useT()
  const [from, setFrom] = useState(iso(new Date(Date.now() - 30 * 864e5)))
  const [to, setTo] = useState(iso(new Date()))
  const [rows, setRows] = useState<Row[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [only, setOnly] = useState<string | null>(null)
  const [q, setQ] = useState("")

  const load = useCallback(async () => {
    setErr(null)
    try {
      const out = await call<Row[]>("kamra.reports.void_allowance_report", {
        property: getCurrentProperty(),
        from_date: from || undefined,
        to_date: to || undefined,
      })
      setRows(out)
    } catch (e) {
      setErr(serverError(e))
      setRows([])
    }
  }, [from, to])

  useEffect(() => {
    void load()
  }, [load])

  const counts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const r of rows ?? []) m[r.action] = (m[r.action] ?? 0) + 1
    return m
  }, [rows])

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (rows ?? []).filter(
      (r) =>
        (!only || r.action === only) &&
        (!s || `${r.actor} ${r.folio ?? ""} ${r.detail ?? ""}`.toLowerCase().includes(s)),
    )
  }, [rows, only, q])

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
            {t("Reports")}
          </p>
          <h1 className="text-2xl font-semibold">{t("Voids & Allowances")}</h1>
          <p className="text-sm text-zinc-500">
            {t("Every void, allowance and cancelled invoice: who, when and why.")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <input
            type="date"
            aria-label={t("From")}
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
          <span className="text-xs text-zinc-400">{t("to")}</span>
          <input
            type="date"
            aria-label={t("To")}
            className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden /> {t("Print")}
          </Button>
        </div>
      </div>
      {err ? <p className="text-sm text-rose-600">{err}</p> : null}

      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <button
          type="button"
          onClick={() => setOnly(null)}
          className={`rounded-full border px-3 py-1 text-xs ${
            only === null ? "border-brand-600 bg-brand-50 text-brand-800" : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
          }`}
        >
          {t("All")} · {rows?.length ?? 0}
        </button>
        {ACTIONS.map((a) => (
          <button
            key={a}
            type="button"
            onClick={() => setOnly(only === a ? null : a)}
            className={`rounded-full border px-3 py-1 text-xs ${
              only === a ? "border-brand-600 bg-brand-50 text-brand-800" : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
            }`}
          >
            {t(a)} · {counts[a] ?? 0}
          </button>
        ))}
        <label className="relative ms-auto">
          <Search className="pointer-events-none absolute start-2 top-2 size-4 text-zinc-400" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("Search folio, staff or reason")}
            className="w-64 rounded-lg border border-zinc-300 bg-white py-1.5 ps-8 pe-2 text-sm"
          />
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2">{t("When")}</th>
              <th className="px-3 py-2">{t("Action")}</th>
              <th className="px-3 py-2">{t("Folio")}</th>
              <th className="px-3 py-2">{t("By")}</th>
              <th className="px-3 py-2">{t("Detail")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rows === null ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-zinc-400">{t("Loading…")}</td>
              </tr>
            ) : shown.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-zinc-400">
                  {t("No voids, allowances or cancelled invoices in this window.")}
                </td>
              </tr>
            ) : (
              shown.map((r, i) => (
                <tr key={`${r.when}-${i}`} className="align-top">
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums text-zinc-500">{r.when.slice(0, 16)}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        r.action === "Void"
                          ? "bg-rose-50 text-rose-700"
                          : r.action === "Allowance"
                            ? "bg-amber-50 text-amber-800"
                            : "bg-zinc-100 text-zinc-700"
                      }`}
                    >
                      {t(r.action)}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {r.folio ? (
                      <Link className="text-brand-700 hover:underline" to={`/billing/${encodeURIComponent(r.folio)}`}>
                        {r.folio}
                      </Link>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-zinc-600">{r.actor}</td>
                  <td className="px-3 py-2 text-zinc-700">{r.detail ?? "-"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
