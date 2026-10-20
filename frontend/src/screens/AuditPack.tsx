/*  The audit pack: the End of Day's final reports, read from the JSON the
    night audit saved on its Night Audit Run - so a past night prints
    exactly what was printed that night. One report at a time with Print /
    Download PDF (the browser's Save as PDF), or Print all as one A4 run. */

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { ArrowLeft, Download, Printer } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { auditPack, type Pack, type PackResponse } from "../lib/eod"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card } from "../components/ui/card"
import { Badge } from "../components/ui/badge"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"

/* eslint-disable @typescript-eslint/no-explicit-any */

const money = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export const fmtDay = (d: unknown) =>
  d
    ? new Date(String(d).slice(0, 10) + "T00:00:00").toLocaleDateString(moneyLocale(), {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "-"

export interface Col {
  key: string
  label: string
  kind?: "money" | "num" | "date" | "text"
  render?: (row: any) => ReactNode
}

export function DataTable({
  cols,
  rows,
  empty,
  total,
  dense,
}: {
  cols: Col[]
  rows: any[]
  empty?: string
  total?: Record<string, ReactNode>
  dense?: boolean
}) {
  const { t } = useT()
  const cell = (c: Col, r: any) => {
    if (c.render) return c.render(r)
    const v = r?.[c.key]
    if (v === null || v === undefined || v === "") return "-"
    if (c.kind === "money") return money(v)
    if (c.kind === "date") return <span className="whitespace-nowrap">{fmtDay(v)}</span>
    return String(v)
  }
  const right = (c: Col) => (c.kind === "money" || c.kind === "num" ? "text-end tabular-nums" : "")
  return (
    <div className="overflow-x-auto print:overflow-visible">
      <table className={cn("w-full table-fixed text-sm", dense && "text-xs")}>
        <thead>
          <tr className="border-b border-zinc-200 text-start text-[11px] font-medium uppercase tracking-wider text-zinc-500">
            {cols.map((c, i) => (
              <th
                key={c.key}
                className={cn(
                  "px-2 py-1.5 text-start",
                  right(c),
                  i === 0 && "w-[24%]",
                )}
              >
                {t(c.label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((r, i) => (
            <tr key={i} className="break-inside-avoid">
              {cols.map((c) => (
                <td key={c.key} className={cn("px-2 py-1.5 align-top", right(c))}>
                  {cell(c, r)}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={cols.length} className="px-2 py-4 text-center text-zinc-400">
                {t(empty ?? "Nothing to report.")}
              </td>
            </tr>
          )}
        </tbody>
        {total && rows.length > 0 && (
          <tfoot>
            <tr className="border-t-2 border-zinc-300 font-semibold">
              {cols.map((c) => (
                <td key={c.key} className={cn("px-2 py-1.5", right(c))}>
                  {total[c.key] ?? ""}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

const sum = (rows: any[], key: string) =>
  rows.reduce((a, r) => a + Number(r?.[key] ?? 0), 0)

function Sub({ children }: { children: ReactNode }) {
  return (
    <h4 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wider text-zinc-500">
      {children}
    </h4>
  )
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  const { t } = useT()
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t(label)}</div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-900">{value}</div>
    </div>
  )
}

/* --- the reports ---------------------------------------------------------- */

function ManagerFlash({ p }: { p: Pack }) {
  const { t } = useT()
  const f = p.manager_flash || {}
  const today = f.today || p.statistics || {}
  const mtd = f.mtd || {}
  const mv = f.movement || {}
  const modes = f.collections?.modes || []
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Occupancy" value={`${today.occupancy_pct ?? 0}%`} />
        <Stat label="ADR" value={`${cur()}${money(today.adr)}`} />
        <Stat label="RevPAR" value={`${cur()}${money(today.revpar)}`} />
        <Stat label="Total revenue" value={`${cur()}${money(today.total_revenue)}`} />
      </div>
      <Sub>{t("Day and month to date")}</Sub>
      <DataTable
        cols={[
          { key: "label", label: "" },
          { key: "rooms_sold", label: "Rooms sold", kind: "num" },
          { key: "occupancy_pct", label: "Occ %", kind: "num" },
          { key: "room_revenue", label: "Room revenue", kind: "money" },
          { key: "fnb_revenue", label: "F&B revenue", kind: "money" },
          { key: "other_revenue", label: "Other revenue", kind: "money" },
          { key: "adr", label: "ADR", kind: "money" },
          { key: "revpar", label: "RevPAR", kind: "money" },
        ]}
        rows={[
          { label: t("Day"), ...today },
          { label: t("Month to date"), ...mtd },
        ]}
      />
      <Sub>{t("Movement")}</Sub>
      <DataTable
        cols={[
          { key: "arrivals", label: "Arrivals", kind: "num" },
          { key: "departures", label: "Departures", kind: "num" },
          { key: "in_house", label: "In house", kind: "num" },
          { key: "no_shows", label: "No-shows", kind: "num" },
        ]}
        rows={[mv]}
      />
      <Sub>{t("Collections by mode")}</Sub>
      <DataTable
        cols={[
          { key: "mode", label: "Mode" },
          { key: "txns", label: "Transactions", kind: "num" },
          { key: "total", label: "Amount", kind: "money" },
        ]}
        rows={modes}
        total={{ mode: t("Total"), total: money(sum(modes, "total")) }}
      />
    </div>
  )
}

function Journal({ p }: { p: Pack }) {
  const { t } = useT()
  const j = p.journal || { lines: [], subtotals: [] }
  const byCashier = useMemo(() => {
    const m = new Map<string, any[]>()
    for (const l of j.lines || []) {
      const k = l.cashier || "-"
      if (!m.has(k)) m.set(k, [])
      m.get(k)!.push(l)
    }
    return [...m.entries()]
  }, [j])
  const cols: Col[] = [
    { key: "date", label: "Date", kind: "date" },
    { key: "time", label: "Time" },
    { key: "room", label: "Room" },
    { key: "guest_name", label: "Guest" },
    { key: "transaction_code", label: "Code" },
    { key: "description", label: "Description" },
    { key: "debit", label: "Debit", kind: "money" },
    { key: "credit", label: "Credit", kind: "money" },
    { key: "cashier", label: "Cashier" },
  ]
  return (
    <div>
      {byCashier.length === 0 && <p className="text-sm text-zinc-400">{t("No postings on this business date.")}</p>}
      {byCashier.map(([cashier, lines]) => (
        <div key={cashier} className="mb-4">
          <Sub>{t("Cashier {c}", { c: cashier })}</Sub>
          <DataTable
            dense
            cols={cols}
            rows={lines}
            total={{
              description: t("Cashier total"),
              debit: money(sum(lines, "debit")),
              credit: money(sum(lines, "credit")),
            }}
          />
        </div>
      ))}
      <Sub>{t("Subtotals by cashier and transaction code")}</Sub>
      <DataTable
        dense
        cols={[
          { key: "cashier", label: "Cashier" },
          { key: "transaction_code", label: "Code" },
          { key: "description", label: "Description" },
          { key: "entries", label: "Entries", kind: "num" },
          { key: "debit", label: "Debit", kind: "money" },
          { key: "credit", label: "Credit", kind: "money" },
        ]}
        rows={j.subtotals || []}
        total={{
          description: t("Total"),
          debit: money(j.total_debit),
          credit: money(j.total_credit),
        }}
      />
    </div>
  )
}

export const SESSION_COLS: Col[] = [
  { key: "cashier_id", label: "Cashier", render: (r) => r.cashier_id || r.user_name || r.user },
  { key: "status", label: "Status" },
  { key: "opening_float", label: "Float", kind: "money" },
  { key: "cash", label: "Cash", kind: "money" },
  { key: "card", label: "Card", kind: "money" },
  { key: "upi", label: "UPI", kind: "money" },
  { key: "paid_outs", label: "Paid out", kind: "money" },
  { key: "expected_cash", label: "Expected", kind: "money" },
  { key: "counted_cash", label: "Counted", kind: "money" },
  { key: "variance", label: "Variance", kind: "money" },
]

function CashierSummary({ p }: { p: Pack }) {
  const rows = p.cashier_sessions || []
  return (
    <DataTable
      cols={SESSION_COLS}
      rows={rows}
      empty="No cashier sessions on this business date."
      total={{
        cashier_id: "Total",
        cash: money(sum(rows, "cash")),
        card: money(sum(rows, "card")),
        upi: money(sum(rows, "upi")),
        expected_cash: money(sum(rows, "expected_cash")),
        counted_cash: money(sum(rows, "counted_cash")),
        variance: money(sum(rows, "variance")),
      }}
    />
  )
}

function GuestLedger({ p }: { p: Pack }) {
  const rows = p.in_house || []
  return (
    <DataTable
      cols={[
        { key: "room", label: "Room" },
        { key: "guest_name", label: "Guest" },
        { key: "reservation", label: "Confirmation" },
        { key: "check_in_date", label: "Arrival", kind: "date" },
        { key: "check_out_date", label: "Departure", kind: "date" },
        { key: "rate", label: "Rate", kind: "money" },
        { key: "folio", label: "Folio" },
        { key: "balance", label: "Balance", kind: "money" },
      ]}
      rows={rows}
      empty="No guests in house."
      total={{ room: "Total", balance: money(sum(rows, "balance")) }}
    />
  )
}

function CityLedger({ p }: { p: Pack }) {
  const rows = p.city_ledger?.accounts || []
  // packs saved before due-date aging only carry the invoice-age buckets
  const byDue = rows.length === 0 || "not_due" in rows[0]
  return (
    <DataTable
      cols={
        byDue
          ? [
              { key: "company", label: "Company" },
              { key: "account_number", label: "Account" },
              { key: "credit_limit", label: "Credit limit", kind: "money" },
              { key: "credit_days", label: "Terms (days)" },
              { key: "not_due", label: "Not due", kind: "money" },
              { key: "d1_30", label: "1-30 overdue", kind: "money" },
              { key: "d31_60", label: "31-60", kind: "money" },
              { key: "d61_90", label: "61-90", kind: "money" },
              { key: "d90p", label: "90+", kind: "money" },
              { key: "open_balance", label: "Open balance", kind: "money" },
            ]
          : [
              { key: "company", label: "Company" },
              { key: "account_number", label: "Account" },
              { key: "credit_limit", label: "Credit limit", kind: "money" },
              { key: "current", label: "0-30", kind: "money" },
              { key: "b30", label: "31-60", kind: "money" },
              { key: "b60", label: "61-90", kind: "money" },
              { key: "b90", label: "91-120", kind: "money" },
              { key: "b90p", label: "120+", kind: "money" },
              { key: "open_balance", label: "Open balance", kind: "money" },
            ]
      }
      rows={rows}
      empty="No city ledger accounts."
      total={{ company: "Total", open_balance: money(sum(rows, "open_balance")) }}
    />
  )
}

function DepositLedger({ p }: { p: Pack }) {
  const d = p.deposit_ledger || { items: [] }
  return (
    <DataTable
      cols={[
        { key: "reservation", label: "Confirmation" },
        { key: "guest_name", label: "Guest" },
        { key: "check_in_date", label: "Arrival", kind: "date" },
        { key: "status", label: "Status" },
        { key: "folio", label: "Folio" },
        { key: "balance", label: "Balance", kind: "money" },
      ]}
      rows={d.items || []}
      empty="No deposits held."
      total={{ reservation: "Total", balance: money(d.total) }}
    />
  )
}

function TrialBalance({ p }: { p: Pack }) {
  const { t } = useT()
  const tb = p.ledger_balances || { ledgers: [] }
  const codes = p.revenue_by_transaction_code?.rows || []
  return (
    <div>
      <DataTable
        cols={[
          { key: "ledger", label: "Ledger" },
          { key: "debit", label: "Debit", kind: "money" },
          { key: "credit", label: "Credit", kind: "money" },
          { key: "balance", label: "Balance", kind: "money" },
        ]}
        rows={tb.ledgers || []}
        total={{
          ledger: t("Total"),
          debit: money(tb.total_debit),
          credit: money(tb.total_credit),
          // a pack carries the folio reconciliation from this release on;
          // an older pack's in_balance compared debits with credits, which
          // never match while guests owe money - show the net instead
          balance: tb.reconciliation
            ? tb.in_balance
              ? t("Agrees with folios")
              : t("Differs from folios by {amount}", { amount: money(tb.reconciliation.difference) })
            : money(Number(tb.total_debit ?? 0) - Number(tb.total_credit ?? 0)),
        }}
      />
      <Sub>{t("Revenue by transaction code")}</Sub>
      <DataTable
        cols={[
          { key: "transaction_code", label: "Code" },
          { key: "description", label: "Description" },
          { key: "entries", label: "Entries", kind: "num" },
          { key: "debit", label: "Debit", kind: "money" },
          { key: "credit", label: "Credit", kind: "money" },
        ]}
        rows={codes}
        total={{ description: t("Total"), debit: money(sum(codes, "debit")), credit: money(sum(codes, "credit")) }}
      />
    </div>
  )
}

function Occupancy({ p }: { p: Pack }) {
  const { t } = useT()
  const s = p.statistics || {}
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Occupancy" value={`${s.occupancy_pct ?? 0}%`} />
        <Stat label="Rooms sold" value={`${s.rooms_sold ?? 0} / ${s.total_rooms ?? 0}`} />
        <Stat label="ADR" value={`${cur()}${money(s.adr)}`} />
        <Stat label="RevPAR" value={`${cur()}${money(s.revpar)}`} />
      </div>
      <Sub>{t("Revenue")}</Sub>
      <DataTable
        cols={[
          { key: "room_revenue", label: "Room", kind: "money" },
          { key: "fnb_revenue", label: "F&B", kind: "money" },
          { key: "other_revenue", label: "Other", kind: "money" },
          { key: "total_revenue", label: "Total", kind: "money" },
          { key: "pax", label: "Guests", kind: "num" },
          { key: "revpax", label: "RevPAX", kind: "money" },
        ]}
        rows={[s]}
      />
      <Sub>{t("Arrivals")}</Sub>
      <DataTable cols={MOVE_COLS} rows={p.arrivals || []} dense />
      <Sub>{t("Departures")}</Sub>
      <DataTable cols={MOVE_COLS} rows={p.departures || []} dense />
    </div>
  )
}

const MOVE_COLS: Col[] = [
  { key: "reservation", label: "Confirmation" },
  { key: "guest_name", label: "Guest" },
  { key: "room", label: "Room" },
  { key: "room_type", label: "Room type" },
  { key: "check_in_date", label: "Arrival", kind: "date" },
  { key: "check_out_date", label: "Departure", kind: "date" },
  { key: "status", label: "Status" },
  { key: "source", label: "Source" },
]

function NoShows({ p }: { p: Pack }) {
  const { t } = useT()
  return (
    <div>
      <Sub>{t("No-shows")}</Sub>
      <DataTable
        cols={[
          { key: "reservation", label: "Confirmation" },
          { key: "guest_name", label: "Guest" },
          { key: "room_type", label: "Room type" },
          { key: "check_in_date", label: "Arrival", kind: "date" },
          { key: "source", label: "Source" },
          { key: "outcome", label: "Policy outcome" },
          { key: "fee_amount", label: "Fee", kind: "money" },
        ]}
        rows={p.no_shows || []}
        empty="No no-shows."
      />
      <Sub>{t("Held late arrivals")}</Sub>
      <DataTable
        cols={[
          { key: "reservation", label: "Confirmation" },
          { key: "guest_name", label: "Guest" },
          { key: "eta", label: "ETA" },
          { key: "reason", label: "Reason" },
        ]}
        rows={p.held_late_arrivals || []}
        empty="None held."
      />
      <Sub>{t("Cancellations")}</Sub>
      <DataTable
        cols={[
          { key: "reservation", label: "Confirmation" },
          { key: "cancellation_number", label: "Cancellation no" },
          { key: "guest_name", label: "Guest" },
          { key: "check_in_date", label: "Arrival", kind: "date" },
          { key: "reason", label: "Reason" },
          { key: "fee", label: "Fee", kind: "money" },
        ]}
        rows={p.cancellations || []}
        empty="No cancellations."
      />
    </div>
  )
}

function RateVariance({ p }: { p: Pack }) {
  const { t } = useT()
  const rv = p.rate_variance?.items || []
  const zero = (p.prechecks || []).find((c: any) => c.key === "zero_rate")?.items || []
  return (
    <div>
      <DataTable
        cols={[
          { key: "room", label: "Room" },
          { key: "guest_name", label: "Guest" },
          { key: "reservation", label: "Confirmation" },
          { key: "expected", label: "Booked rate", kind: "money" },
          { key: "posted", label: "Posted", kind: "money" },
          { key: "difference", label: "Difference", kind: "money" },
          { key: "manual", label: "Manual", render: (r) => (r.manual ? t("Yes") : t("No")) },
        ]}
        rows={rv}
        empty="Every room night was posted at its booked rate."
      />
      <Sub>{t("Zero-rate and complimentary rooms")}</Sub>
      <DataTable
        cols={[
          { key: "room", label: "Room" },
          { key: "guest_name", label: "Guest" },
          { key: "reservation", label: "Confirmation" },
          { key: "rate_plan", label: "Rate plan" },
        ]}
        rows={zero}
        empty="None."
      />
    </div>
  )
}

function Exceptions({ p }: { p: Pack }) {
  const { t } = useT()
  return (
    <div>
      {p.notes && (
        <div className="mb-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500">{t("Notes for the manager")}</div>
          <p className="mt-1 whitespace-pre-wrap">{p.notes}</p>
        </div>
      )}
      <DataTable
        cols={[
          { key: "title", label: "Check", render: (r) => t(r.title) },
          { key: "severity", label: "Severity", render: (r) => t(r.severity) },
          { key: "count", label: "Items", kind: "num" },
          {
            key: "acknowledgement",
            label: "Acknowledged",
            render: (r) =>
              r.acknowledgement
                ? `${r.acknowledgement.by_name || r.acknowledgement.by} · ${String(r.acknowledgement.at).slice(0, 16)} · ${r.acknowledgement.note}`
                : r.exception
                  ? t("Not acknowledged")
                  : "-",
          },
        ]}
        rows={p.prechecks || []}
      />
    </div>
  )
}

export const REPORTS: { key: string; title: string; Body: (props: { p: Pack }) => ReactNode }[] = [
  { key: "manager_flash", title: "Manager's flash", Body: ManagerFlash },
  { key: "journal", title: "Journal by cashier and transaction code", Body: Journal },
  { key: "cashier_summary", title: "Cashier summary", Body: CashierSummary },
  { key: "guest_ledger", title: "Guest ledger detail", Body: GuestLedger },
  { key: "city_ledger", title: "City ledger / AR summary", Body: CityLedger },
  { key: "deposit_ledger", title: "Deposit ledger balance", Body: DepositLedger },
  { key: "trial_balance", title: "Trial balance", Body: TrialBalance },
  { key: "occupancy", title: "Occupancy & revenue", Body: Occupancy },
  { key: "no_shows", title: "No-shows and cancellations", Body: NoShows },
  { key: "rate_variance", title: "Rate variance", Body: RateVariance },
  { key: "exceptions", title: "Pre-checks and exceptions", Body: Exceptions },
]

function ReportSheet({ p, report, first }: { p: Pack; report: (typeof REPORTS)[number]; first: boolean }) {
  const { t } = useT()
  const Body = report.Body
  return (
    <section className={cn("audit-sheet", !first && "print:break-before-page")}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2 border-b border-zinc-200 pb-2">
        <div>
          <div className="text-xs text-zinc-500">{p.property_name}{p.city ? ` · ${p.city}` : ""}</div>
          <h3 className="text-base font-semibold text-zinc-900">{t(report.title)}</h3>
        </div>
        <div className="text-end text-xs text-zinc-500">
          <div>{t("Business date {d}", { d: fmtDay(p.business_date) })}</div>
          <div>{t("Printed from the audit pack of {when}", { when: String(p.generated_at || "").slice(0, 16) })}</div>
        </div>
      </div>
      <Body p={p} />
    </section>
  )
}

export function AuditPackView({ audit, embedded = false }: { audit: string; embedded?: boolean }) {
  const { t } = useT()
  const [data, setData] = useState<PackResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [active, setActive] = useState(REPORTS[0].key)
  const [all, setAll] = useState(false)

  useEffect(() => {
    setData(null)
    auditPack(audit).then(setData).catch((e) => setErr(serverError(e)))
  }, [audit])

  useEffect(() => {
    const done = () => setAll(false)
    window.addEventListener("afterprint", done)
    return () => window.removeEventListener("afterprint", done)
  }, [])

  const print = (everything: boolean) => {
    setAll(everything)
    setTimeout(() => window.print(), 60)
  }

  if (err) return <p className="text-sm text-rose-600">{err}</p>
  if (!data) return <p className="text-sm text-zinc-400">{t("Loading the audit pack…")}</p>
  if (!data.has_pack || !data.pack)
    return (
      <Card className="p-5 text-sm text-zinc-600">
        {t("No audit pack was saved for this run - it ran before audit packs were introduced.")}
      </Card>
    )
  const p = data.pack
  const shown = all ? REPORTS : REPORTS.filter((r) => r.key === active)
  return (
    <div className={cn("grid gap-4 print:block", !embedded && "lg:grid-cols-[260px_1fr]", embedded && "2xl:grid-cols-[240px_1fr]")}>
      <Card className="h-fit p-2 print:hidden">
        <div className="px-2 pb-1 pt-1 text-xs font-medium uppercase tracking-wider text-zinc-400">
          {t("Final reports")}
        </div>
        <ul className={cn(embedded && "flex flex-wrap gap-1 2xl:block")}>
          {REPORTS.map((r) => (
            <li key={r.key}>
              <button
                type="button"
                onClick={() => setActive(r.key)}
                className={cn(
                  "rounded-lg px-2 py-1.5 text-start text-sm hover:bg-zinc-100",
                  embedded ? "2xl:w-full" : "w-full",
                  active === r.key && "bg-brand-50 font-medium text-brand-700",
                )}
              >
                {t(r.title)}
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-2 border-t border-zinc-100 p-2">
          <Button className="w-full" onClick={() => print(true)}>
            <Printer className="size-4" aria-hidden />
            {t("Print all")}
          </Button>
        </div>
      </Card>
      <Card className="min-w-0 p-5 print:border-0 print:p-0 print:shadow-none">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 print:hidden">
          <div className="flex items-center gap-2">
            <Badge tone={String(data.run.status).includes("Warnings") ? "amber" : "green"}>
              {t(String(data.run.status))}
            </Badge>
            <span className="text-xs text-zinc-500">{data.audit}</span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => print(false)}>
              <Printer className="size-4" aria-hidden />
              {t("Print")}
            </Button>
            <Button variant="outline" onClick={() => print(false)} title={t("Choose Save as PDF in the print dialog")}>
              <Download className="size-4" aria-hidden />
              {t("Download PDF")}
            </Button>
          </div>
        </div>
        <div className="space-y-8">
          {shown.map((r, i) => (
            <ReportSheet key={r.key} p={p} report={r} first={i === 0} />
          ))}
        </div>
      </Card>
    </div>
  )
}

export default function AuditPackScreen() {
  const { t } = useT()
  const { audit = "" } = useParams()
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <Link to="/end-of-day" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft className="size-4" aria-hidden />
          {t("End of Day")}
        </Link>
        <span className="text-xs text-zinc-400">{audit}</span>
      </div>
      <AuditPackView audit={decodeURIComponent(audit)} />
    </div>
  )
}
