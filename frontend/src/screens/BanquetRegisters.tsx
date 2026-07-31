/*  The books a banquet office keeps.

    Five listings that every hall has kept on paper forever — what's
    booked, what was quoted, what came in, what was collected, what it all
    added up to. The old software made you pick a radio button and hit
    Print; here you pick a period once and the whole set is a tab away,
    on screen, sortable, and printable when you actually need paper. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Download, Printer, ScrollText } from "lucide-react"

import { banquet, type BanquetRegister, type RegisterRollup } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import {
  Empty,
  ErrorNote,
  Field,
  inputCls,
  inr,
  StatusPill,
  today,
} from "./banquet/shared"

const REGISTERS = [
  ["functions", "Functions", "Everything booked in the period"],
  ["quotations", "Quotations", "What was quoted, and whether it landed"],
  ["enquiries", "Enquiries", "What came in, and what happened to it"],
  ["receipts", "Cash book", "Every payment, by mode"],
  ["sales", "Sales summary", "Revenue by hall, event type and session"],
] as const
type Reg = (typeof REGISTERS)[number][0]

/** First and last day of the month a date falls in — the period a banquet
 *  office almost always wants, so it's the default. */
function monthBounds(iso: string) {
  const d = new Date(iso + "T00:00:00")
  const first = new Date(d.getFullYear(), d.getMonth(), 1)
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  const fmt = (x: Date) =>
    `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(
      x.getDate(),
    ).padStart(2, "0")}`
  return [fmt(first), fmt(last)] as const
}

export default function BanquetRegisters() {
  const navigate = useNavigate()
  const [defaultFrom, defaultTo] = useMemo(() => monthBounds(today()), [])
  const [from, setFrom] = useState(defaultFrom)
  const [to, setTo] = useState(defaultTo)
  const [reg, setReg] = useState<Reg>("functions")
  const [data, setData] = useState<BanquetRegister | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setData(null)
    banquet
      .register(reg, from, to)
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [reg, from, to])
  useEffect(load, [load])

  /** A register is a table of numbers; people paste them into spreadsheets.
   *  Giving them a real CSV beats them retyping it. */
  function exportCsv() {
    if (!data?.rows.length) return
    const cols = Object.keys(data.rows[0] as unknown as object).filter(
      (k) => !["lost_reason"].includes(k),
    )
    const esc = (v: unknown) =>
      `"${String(v ?? "").replace(/"/g, '""')}"`
    const csv = [
      cols.join(","),
      ...data.rows.map((r) =>
        cols.map((c) => esc((r as unknown as Record<string, unknown>)[c])).join(","),
      ),
    ].join("\n")
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }))
    const a = document.createElement("a")
    a.href = url
    a.download = `banquet-${reg}-${from}-to-${to}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Card>
      <CardHeader className="print:hidden">
        <div>
          <CardTitle>
            <span className="inline-flex items-center gap-1.5">
              <ScrollText className="size-4" />
              Banquet registers
            </span>
          </CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            Pick the period once — every book is a tab away.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="From">
            <input
              type="date"
              className={inputCls + " !w-36"}
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </Field>
          <Field label="To">
            <input
              type="date"
              className={inputCls + " !w-36"}
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </Field>
          <Button variant="outline" onClick={exportCsv} disabled={!data?.rows.length}>
            <Download className="size-4" />
            CSV
          </Button>
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="size-4" />
            Print
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ErrorNote error={error} />

        <div className="mb-4 flex flex-wrap gap-1 border-b border-zinc-200 print:hidden">
          {REGISTERS.map(([id, label, blurb]) => (
            <button
              key={id}
              onClick={() => setReg(id)}
              title={blurb}
              className={
                "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors " +
                (reg === id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-zinc-500 hover:text-zinc-800")
              }
            >
              {label}
            </button>
          ))}
        </div>

        {/* the print header - on screen the toolbar already says all this */}
        <div className="mb-3 hidden print:block">
          <h2 className="text-base font-semibold">{data?.title}</h2>
          <p className="text-xs text-zinc-500">
            {from} to {to}
          </p>
        </div>

        {!data ? (
          <Empty>Loading…</Empty>
        ) : data.rows.length === 0 ? (
          <Empty>Nothing in this period.</Empty>
        ) : (
          <>
            <Totals data={data} />
            {reg === "sales" ? (
              <SalesSummary data={data} />
            ) : reg === "receipts" ? (
              <CashBook data={data} />
            ) : (
              <FunctionList
                data={data}
                onOpen={(n) => navigate(`/banquet/${encodeURIComponent(n)}`)}
              />
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function Totals({ data }: { data: BanquetRegister }) {
  const t = data.totals
  const cells: [string, string][] = [
    ["Rows", String(t.count)],
    ...(t.pax !== undefined ? ([["Pax", String(t.pax)]] as [string, string][]) : []),
    ["Value", inr(t.value)],
    ...(t.received !== undefined
      ? ([["Received", inr(t.received)]] as [string, string][])
      : []),
    ...(t.outstanding !== undefined
      ? ([["Outstanding", inr(t.outstanding)]] as [string, string][])
      : []),
  ]
  return (
    <div className="mb-4 flex flex-wrap gap-x-8 gap-y-2 rounded-xl bg-zinc-50 px-4 py-3">
      {cells.map(([k, v]) => (
        <div key={k}>
          <p className="text-[11px] uppercase tracking-wider text-zinc-400">{k}</p>
          <p className="text-lg font-semibold tabular-nums">{v}</p>
        </div>
      ))}
    </div>
  )
}

function FunctionList({
  data,
  onOpen,
}: {
  data: BanquetRegister
  onOpen: (name: string) => void
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
            <th className="py-2 pr-3 font-medium">Ref</th>
            <th className="py-2 pr-3 font-medium">Date</th>
            <th className="py-2 pr-3 font-medium">Customer</th>
            <th className="py-2 pr-3 font-medium">Hall / session</th>
            <th className="py-2 pr-3 font-medium">Event</th>
            <th className="py-2 pr-3 text-right font-medium">Pax</th>
            <th className="py-2 pr-3 text-right font-medium">Rate/pax</th>
            <th className="py-2 pr-3 text-right font-medium">Value</th>
            <th className="py-2 pr-3 text-right font-medium">Due</th>
            <th className="py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr
              key={r.name}
              onClick={() => onOpen(r.name)}
              className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50"
            >
              <td className="py-1.5 pr-3 font-mono text-xs text-zinc-400">
                {r.name}
              </td>
              <td className="py-1.5 pr-3 whitespace-nowrap tabular-nums">
                {r.event_date}
              </td>
              <td className="py-1.5 pr-3">
                <div className="font-medium">{r.customer_name}</div>
                {r.company && (
                  <div className="text-xs text-zinc-400">{r.company}</div>
                )}
              </td>
              <td className="py-1.5 pr-3 text-zinc-600">
                {r.venue}
                <span className="text-zinc-400"> · {r.session}</span>
              </td>
              <td className="py-1.5 pr-3 text-zinc-600">
                {r.event_name || r.event_type}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {r.pax || "-"}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums text-zinc-500">
                {r.rate_per_pax ? inr(r.rate_per_pax) : "-"}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {inr(r.grand_total)}
              </td>
              <td
                className={
                  "py-1.5 pr-3 text-right tabular-nums " +
                  (r.balance_due > 0 ? "text-rose-700" : "text-zinc-300")
                }
              >
                {r.balance_due > 0 ? inr(r.balance_due) : "—"}
              </td>
              <td className="py-1.5">
                <StatusPill status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CashBook({ data }: { data: BanquetRegister }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
              <th className="py-2 pr-3 font-medium">Date</th>
              <th className="py-2 pr-3 font-medium">Customer</th>
              <th className="py-2 pr-3 font-medium">Hall</th>
              <th className="py-2 pr-3 font-medium">Kind</th>
              <th className="py-2 pr-3 font-medium">Mode</th>
              <th className="py-2 pr-3 font-medium">Reference</th>
              <th className="py-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i} className="border-b border-zinc-100">
                <td className="py-1.5 pr-3 whitespace-nowrap tabular-nums text-zinc-500">
                  {r.receipt_date}
                </td>
                <td className="py-1.5 pr-3">{r.customer_name}</td>
                <td className="py-1.5 pr-3 text-zinc-500">{r.venue}</td>
                <td className="py-1.5 pr-3">{r.kind}</td>
                <td className="py-1.5 pr-3 text-zinc-500">{r.mode}</td>
                <td className="py-1.5 pr-3 text-zinc-400">{r.reference}</td>
                <td
                  className={
                    "py-1.5 text-right tabular-nums " +
                    ((r.signed_amount ?? 0) < 0 ? "text-rose-700" : "")
                  }
                >
                  {inr(r.signed_amount ?? r.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.by_mode && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            By mode
          </h3>
          <ul className="space-y-1.5">
            {data.by_mode.map((m) => (
              <li
                key={m.mode}
                className="flex justify-between rounded-lg bg-zinc-50 px-3 py-2 text-sm"
              >
                <span>{m.mode}</span>
                <span className="font-medium tabular-nums">{inr(m.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function SalesSummary({ data }: { data: BanquetRegister }) {
  const blocks: [string, RegisterRollup[] | undefined][] = [
    ["By hall", data.by_venue],
    ["By event type", data.by_event_type],
    ["By session", data.by_session],
    ["By source", data.by_source],
  ]
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {blocks.map(([title, rows]) =>
        rows?.length ? (
          <div key={title}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
              {title}
            </h3>
            <Bars rows={rows} />
          </div>
        ) : null,
      )}
    </div>
  )
}

function Bars({ rows }: { rows: RegisterRollup[] }) {
  const peak = Math.max(1, ...rows.map((r) => r.value))
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="flex justify-between text-sm">
            <span className="truncate text-zinc-600">{r.key}</span>
            <span className="shrink-0 tabular-nums">
              {inr(r.value)}{" "}
              <span className="text-zinc-400">
                ({r.count} · {r.pax} pax)
              </span>
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full bg-brand-500"
              style={{ width: `${(r.value / peak) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
