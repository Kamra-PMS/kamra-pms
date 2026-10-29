import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Info } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { fmtMoney, taxLabel, useLocale } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"

// Management P&L (/profit-and-loss) and balance sheet (/balance-sheet),
// from kamra.books. Not statutory accounts: the screen says so.

type Line = { key?: string; category?: string; amount: number | null; count?: number }
type PnL = {
  from_date: string
  to_date: string
  revenue: Line[]
  revenue_total: number
  supplier_bills: Line[]
  petty_cash: Line[]
  expense_total: number
  net: number
  tax_collected: number
  tax_on_bills: number
}
type BS = {
  as_of: string
  assets: Line[]
  assets_total: number
  liabilities: Line[]
  liabilities_total: number
  net: number
  tax_month_from: string
  tax_collected_month: number
  tax_on_bills_month: number
}

const LABEL: Record<string, string> = {
  rooms: "Rooms",
  fnb: "Food and beverage",
  banquets: "Banquets",
  other: "Other income",
  allowances: "Allowances",
  cash_in_tills: "Cash in open tills",
  guest_ledger: "Owed by guests in house",
  city_ledger: "Owed by companies (city ledger)",
  advance_deposits: "Advance deposits held",
  payables: "Owed to suppliers",
}

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`

function monthRange(offset: number): [string, string] {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const end = offset === 0 ? now : new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)
  return [iso(start), iso(end)]
}

const input = "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm"

export default function ManagementBooks({ view }: { view: "pnl" | "balance" }) {
  useUILanguage()
  useLocale()
  return (
    <div className="w-full space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
          <h1 className="text-2xl font-semibold">{translate(view === "pnl" ? "Profit and loss" : "Balance sheet")}</h1>
          <p className="text-sm text-zinc-500">{translate("Management view from what Kamra records. Not statutory accounts.")}</p>
        </div>
        <div className="inline-flex rounded-lg border border-zinc-200 p-0.5 text-sm">
          <Link to="/profit-and-loss" className={`rounded-md px-3 py-1 ${view === "pnl" ? "bg-zinc-900 text-white" : "text-zinc-600"}`}>{translate("Profit and loss")}</Link>
          <Link to="/balance-sheet" className={`rounded-md px-3 py-1 ${view === "balance" ? "bg-zinc-900 text-white" : "text-zinc-600"}`}>{translate("Balance sheet")}</Link>
        </div>
      </div>
      {view === "pnl" ? <ProfitAndLoss /> : <BalanceSheet />}
    </div>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-xs text-zinc-600">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  )
}

function Row({ label, amount, strong, muted, indent }: { label: string; amount: number | null; strong?: boolean; muted?: boolean; indent?: boolean }) {
  return (
    <div className={`flex justify-between gap-3 py-1.5 ${strong ? "border-t border-zinc-200 font-semibold" : ""} ${muted ? "text-zinc-500" : ""}`}>
      <span className={indent ? "pl-4" : ""}>{label}</span>
      <span className={`tabular-nums ${amount != null && amount < 0 ? "text-rose-700" : ""}`}>
        {amount == null ? translate("Today only") : fmtMoney(amount)}
      </span>
    </div>
  )
}

function ProfitAndLoss() {
  useUILanguage()
  const [range, setRange] = useState<[string, string]>(() => monthRange(0))
  const [data, setData] = useState<PnL | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(() => {
    setErr(null)
    call<PnL>("kamra.books.profit_and_loss", {
      property: getCurrentProperty(), from_date: range[0], to_date: range[1],
    })
      .then(setData)
      .catch((e) => setErr(serverError(e)))
  }, [range])
  useEffect(load, [load])

  return (
    <>
      <div className="flex flex-wrap items-end gap-2">
        <Button variant="outline" onClick={() => setRange(monthRange(0))}>{translate("This month")}</Button>
        <Button variant="outline" onClick={() => setRange(monthRange(-1))}>{translate("Last month")}</Button>
        <input type="date" className={input} value={range[0]} onChange={(e) => setRange([e.target.value, range[1]])} />
        <span className="pb-2 text-zinc-400">{translate("to")}</span>
        <input type="date" className={input} value={range[1]} onChange={(e) => setRange([range[0], e.target.value])} />
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">{translate("Revenue")}</CardTitle></CardHeader>
            <CardContent className="text-sm">
              {data.revenue.map((r) => <Row key={r.key} label={translate(LABEL[r.key ?? ""] ?? r.key ?? "")} amount={r.amount} />)}
              <Row label={translate("Total revenue")} amount={data.revenue_total} strong />
              <p className="mt-2 text-xs text-zinc-500">{translate("Before tax. Room levy and go-live balances are not revenue.")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">{translate("Expenses")}</CardTitle></CardHeader>
            <CardContent className="text-sm">
              <p className="text-xs font-medium uppercase text-zinc-400">{translate("Supplier bills")}</p>
              {data.supplier_bills.map((r) => <Row key={`b-${r.category}`} label={translate(r.category ?? "")} amount={r.amount} indent />)}
              {!data.supplier_bills.length ? <p className="py-1.5 pl-4 text-zinc-400">{translate("None in this period.")}</p> : null}
              <p className="mt-2 text-xs font-medium uppercase text-zinc-400">{translate("Petty cash")}</p>
              {data.petty_cash.map((r) => <Row key={`p-${r.category}`} label={translate(r.category ?? "")} amount={r.amount} indent />)}
              {!data.petty_cash.length ? <p className="py-1.5 pl-4 text-zinc-400">{translate("None in this period.")}</p> : null}
              <Row label={translate("Total expenses")} amount={data.expense_total} strong />
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardContent className="pt-4 text-sm">
              <Row label={translate("Profit for the period")} amount={data.net} strong />
              <Row label={translate("{v0} collected on bills (owed to the government)", { v0: taxLabel() })} amount={data.tax_collected} muted />
              <Row label={translate("{v0} paid on supplier bills", { v0: taxLabel() })} amount={data.tax_on_bills} muted />
            </CardContent>
          </Card>
        </div>
      ) : null}
      <Note>
        {translate("This is a management P&L. It counts what Kamra records: guest and company bills, restaurant bills, banquets, supplier bills and petty cash. Payroll, depreciation, loans and anything paid outside Kamra are not in it. Your accountant keeps the statutory books from the Accounting Export.")}
      </Note>
    </>
  )
}

function BalanceSheet() {
  useUILanguage()
  const [asOf, setAsOf] = useState(() => iso(new Date()))
  const [data, setData] = useState<BS | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(() => {
    setErr(null)
    call<BS>("kamra.books.balance_sheet", { property: getCurrentProperty(), as_of: asOf })
      .then(setData)
      .catch((e) => setErr(serverError(e)))
  }, [asOf])
  useEffect(load, [load])

  return (
    <>
      <label className="flex items-center gap-2 text-sm text-zinc-600">
        {translate("As of")}
        <input type="date" className={input} value={asOf} max={iso(new Date())} onChange={(e) => setAsOf(e.target.value)} />
      </label>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">{translate("Owed to the hotel")}</CardTitle></CardHeader>
            <CardContent className="text-sm">
              {data.assets.map((r) => <Row key={r.key} label={translate(LABEL[r.key ?? ""] ?? r.key ?? "")} amount={r.amount} />)}
              <Row label={translate("Total")} amount={data.assets_total} strong />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">{translate("Owed by the hotel")}</CardTitle></CardHeader>
            <CardContent className="text-sm">
              {data.liabilities.map((r) => <Row key={r.key} label={translate(LABEL[r.key ?? ""] ?? r.key ?? "")} amount={r.amount} />)}
              <Row label={translate("Total")} amount={data.liabilities_total} strong />
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardContent className="pt-4 text-sm">
              <Row label={translate("Owed to the hotel, less owed by it")} amount={data.net} strong />
              <Row label={translate("{v0} collected since {v1}", { v0: taxLabel(), v1: data.tax_month_from })} amount={data.tax_collected_month} muted />
              <Row label={translate("{v0} paid on supplier bills since {v1}", { v0: taxLabel(), v1: data.tax_month_from })} amount={data.tax_on_bills_month} muted />
            </CardContent>
          </Card>
        </div>
      ) : null}
      <Note>
        {translate("Only what Kamra can see. Your bank balance, fixed assets, loans and equity are not in Kamra, so this is not a full balance sheet. Tax is shown for reference: Kamra does not record what you have paid to the government.")}
      </Note>
    </>
  )
}
