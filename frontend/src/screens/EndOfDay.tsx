/*  Manage End of Day: one card per property the user can reach, with the
    business date, the property's clock and what is still open, then the
    history of past audits (searchable by date) with their audit packs. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { CheckCircle2, FileText, MoonStar, Search, TriangleAlert } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { getCurrentProperty } from "../lib/api"
import { auditHistory, eodOverview, type OverviewRow, type RunRow } from "../lib/eod"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { fmtDay } from "./AuditPack"

const amount = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

function Count({ label, n, warn }: { label: string; n: number; warn?: boolean }) {
  const { t } = useT()
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t(label)}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${n && warn ? "text-rose-600" : "text-zinc-900"}`}>
        {n}
      </div>
    </div>
  )
}

export default function EndOfDay() {
  const { t } = useT()
  const navigate = useNavigate()
  const [rows, setRows] = useState<OverviewRow[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [histProp, setHistProp] = useState(getCurrentProperty())
  const [history, setHistory] = useState<RunRow[]>([])
  const [q, setQ] = useState("")

  useEffect(() => {
    eodOverview()
      .then((r) => {
        setRows(r)
        if (r.length && !r.some((x) => x.property === histProp)) setHistProp(r[0].property)
      })
      .catch((e) => setErr(serverError(e)))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const loadHistory = useCallback(() => {
    if (!histProp) return
    auditHistory(histProp).then(setHistory).catch(() => setHistory([]))
  }, [histProp])
  useEffect(loadHistory, [loadHistory])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return history
    return history.filter((r) =>
      `${r.business_date} ${fmtDay(r.business_date)} ${r.status} ${r.name}`.toLowerCase().includes(s),
    )
  }, [history, q])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900">{t("Manage End of Day / Night Audit")}</h1>
        <p className="text-sm text-zinc-500">
          {t("End of Day is the night audit. Close each property's business date: work through the checklist, post room and tax, roll the date and print the audit pack. The 3 AM job runs the same steps on its own.")}
        </p>
      </div>
      {err && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
      {!rows && !err && <p className="text-sm text-zinc-400">{t("Loading…")}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {(rows ?? []).map((r) => (
          <Card key={r.property}>
            <CardHeader>
              <div>
                <CardTitle>{r.property_name}</CardTitle>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {t("Business date {bd} · property time {now}", {
                    bd: fmtDay(r.business_date),
                    now: r.property_now.slice(11, 16),
                  })}
                </p>
              </div>
              {r.blockers ? (
                <Badge tone="rose">
                  <TriangleAlert className="me-1 size-3" aria-hidden />
                  {t("{n} blocker(s)", { n: r.blockers })}
                </Badge>
              ) : (
                <Badge tone="green">
                  <CheckCircle2 className="me-1 size-3" aria-hidden />
                  {t("Ready")}
                </Badge>
              )}
            </CardHeader>
            <CardContent className="pt-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Count label="Arrivals pending" n={r.arrivals_pending} />
                <Count label="Departures pending" n={r.departures_pending} warn />
                <Count label="Open cashiers" n={r.open_cashiers} warn />
                <Count label="Open POS bills" n={r.open_pos_bills} warn />
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-zinc-500">
                  {r.last_run
                    ? t("Last closed {d}", { d: fmtDay(r.last_run.business_date) })
                    : t("No audit run yet")}
                  {r.draft_step ? ` · ${t("in progress at step {n}", { n: r.draft_step })}` : ""}
                </span>
                <Button onClick={() => navigate(`/end-of-day/${encodeURIComponent(r.property)}`)}>
                  <MoonStar className="size-4" aria-hidden />
                  {r.draft_step ? t("Continue") : t("Manage")}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex-wrap gap-2">
          <CardTitle>{t("Audit history")}</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {(rows?.length ?? 0) > 1 && (
              <select
                className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                value={histProp}
                onChange={(e) => setHistProp(e.target.value)}
                aria-label={t("Property")}
              >
                {rows!.map((r) => (
                  <option key={r.property} value={r.property}>{r.property_name}</option>
                ))}
              </select>
            )}
            <label className="relative">
              <Search className="pointer-events-none absolute start-2 top-2 size-4 text-zinc-400" aria-hidden />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t("Search by date")}
                className="w-48 rounded-lg border border-zinc-300 bg-white py-1.5 ps-8 pe-2 text-sm"
              />
            </label>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-start text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="py-2 pe-3 text-start">{t("Business date")}</th>
                  <th className="py-2 pe-3 text-start">{t("Status")}</th>
                  <th className="py-2 pe-3 text-start">{t("Trigger")}</th>
                  <th className="py-2 pe-3 text-end">{t("Room nights")}</th>
                  <th className="py-2 pe-3 text-end">{t("Posted {cur}", { cur: cur() })}</th>
                  <th className="py-2 pe-3 text-end">{t("No-shows")}</th>
                  <th className="py-2 pe-3 text-end">{t("Exceptions")}</th>
                  <th className="py-2 text-end">{t("Audit pack")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filtered.map((r) => (
                  <tr key={r.name}>
                    <td className="py-2 pe-3 font-medium">{fmtDay(r.business_date)}</td>
                    <td className="py-2 pe-3">
                      <Badge tone={r.status === "Completed" ? "green" : "amber"}>{t(r.status)}</Badge>
                    </td>
                    <td className="py-2 pe-3 text-zinc-500">{t(r.run_trigger || "Manual")}</td>
                    <td className="py-2 pe-3 text-end tabular-nums">{r.room_charges_posted}</td>
                    <td className="py-2 pe-3 text-end tabular-nums">{amount(r.amount_posted)}</td>
                    <td className="py-2 pe-3 text-end tabular-nums">{r.no_shows_flagged}</td>
                    <td className="py-2 pe-3 text-end tabular-nums">{r.exceptions || 0}</td>
                    <td className="py-2 text-end">
                      {r.has_pack ? (
                        <Link
                          to={`/end-of-day/pack/${encodeURIComponent(r.name)}`}
                          className="inline-flex items-center gap-1 text-brand-700 hover:underline"
                        >
                          <FileText className="size-4" aria-hidden />
                          {t("View")}
                        </Link>
                      ) : (
                        <span className="text-xs text-zinc-400">{t("No pack")}</span>
                      )}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-zinc-400">
                      {t("No audits found.")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
