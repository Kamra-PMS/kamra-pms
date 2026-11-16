import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, ChevronDown, Plus, Printer } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { DataTable } from "../components/ui/data-table"
import { Sheet } from "../components/ui/sheet"
import { fmtMoney, loadLocale, taxLabel, useLocale } from "../lib/money"
import { useAuth } from "../lib/auth"
import { downloadCsv } from "../lib/csv"
import CityLedgerPayment from "./CityLedgerPayment"
import { t as translate, useUILanguage } from "../lib/i18n"

// Accounts receivable: the company accounts the hotel bills on credit.
// /receivables lists them; /receivables/:account is one account - its bills,
// payments, and the finance actions (new invoice, payment, transfer,
// statement). Every number comes from kamra.ledger / kamra.receivables.

const FINANCE = ["Finance", "Hotel Admin", "System Manager", "Administrator"]

// what a direct invoice can bill (kamra.ledger.CHARGE_TYPE_TO_CODE, less
// the adjustments, the levy and the go-live opening balance)
const BILLABLE = [
  "Room", "Meal Plan", "Food & Beverage", "Minibar", "Laundry", "Spa",
  "Early Check-in", "Late Checkout", "Cleaning Fee", "Extra Guests",
  "Pet Charge", "Misc",
]

type AccountRow = {
  total_debit?: number
  total_credit?: number
  name: string
  company: string
  company_name: string
  account_number?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  balance: number
  credit_limit: number
  credit_days: number
  overdue: number
  unapplied_credit: number
  restricted: number
  restricted_reason?: string
  unbilled?: number
  last_payment_date?: string | null
  last_payment?: number | null
  not_due?: number; d1_30?: number; d31_60?: number; d61_90?: number; d90p?: number
}

// the work queues on top of the list: each is a filter over the same rows
const QUEUES = {
  all: { label: "All accounts", test: (_r: AccountRow) => true },
  overdue: { label: "Overdue", test: (r: AccountRow) => r.overdue > 0.005 },
  over_limit: { label: "Over credit limit", test: (r: AccountRow) => overLimit(r) },
  unbilled: { label: "In house, not billed", test: (r: AccountRow) => (r.unbilled ?? 0) > 0.005 },
  ahead: { label: "Paid ahead", test: (r: AccountRow) => r.unapplied_credit > 0.005 },
} as const
type Queue = keyof typeof QUEUES

/** Over the limit the way the night audit counts it: what the company owes
 *  plus what its stays in house are running up. */
function overLimit(r: AccountRow) {
  return r.credit_limit > 0 && r.balance + (r.unbilled ?? 0) > r.credit_limit
}

type HistoryRow = {
  name: string; posting_date: string; kind: string; folio?: string | null
  invoice_number?: string | null; guest_name?: string | null; reference?: string | null
  notes?: string | null; debit: number; credit: number; balance: number
  applied: { folio: string; invoice_number?: string | null; guest_name?: string | null; amount: number }[]
}

type GuestOwing = {
  folio: string; guest_name: string; balance: number; reservation: string
  status: string; check_in_date: string; check_out_date: string
}

type Summary = {
  to_bill: number; billed_pending: number; overdue: number
  received_this_month: number; deposits_held: number; guests_owing: GuestOwing[]
}

type OpenItem = {
  folio: string
  invoice_number?: string | null
  invoice_date: string
  due_date?: string
  days_overdue?: number
  guest_name?: string | null
  reservation?: string | null
  folio_type?: string | null
  billed: number
  paid: number
  outstanding: number
  disputed?: number
  dispute_note?: string | null
}

type Payment = {
  name: string
  posting_date: string
  received_on?: string | null
  credit: number
  debit: number
  reference?: string
  notes?: string
  reverses?: string | null
  reversed?: boolean
}

type PendingPayment = {
  name: string
  amount: number
  mode?: string
  reference?: string
  received_on?: string
  allocations?: string
  requested_by: string
  requested_on: string
  channel?: string
}

// a Finance step on the account that needs a note, a reason or a PIN
type Action =
  | { kind: "dispute"; item: OpenItem }
  | { kind: "reverse"; payment: Payment }
  | { kind: "confirm" | "reject"; request: PendingPayment }

type Account = {
  total_debit?: number
  total_credit?: number
  account: string
  company: string
  account_number?: string
  credit_limit: number
  account_credit_days: number
  use_default_credit_days: boolean
  credit_days: number
  billing_address?: string | null
  restricted: boolean
  restricted_reason?: string | null
  balance: number
  in_house: number
  available_credit: number | null
  open_balance: number
  unapplied_credit: number
  overdue: number
  not_due: number
  d1_30: number
  d31_60: number
  d61_90: number
  d90p: number
  disputed?: number
  open_items: OpenItem[]
  // every bill on the account, paid ones included (newer servers)
  bills?: OpenItem[]
  payments: (Payment & {
    applied?: { folio: string; invoice_number?: string; guest_name?: string; amount: number }[]
    unapplied?: number
  })[]
  pending_payments: PendingPayment[]
  cashier_pin_required: boolean
  payment_pin_required?: boolean
}

const field = "w-full rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"

export default function Receivables() {
  const { account } = useParams()
  return account ? <AccountPage account={account} /> : <AccountList />
}

// ── list ────────────────────────────────────────────────────────────────────

function AccountList() {
  const language = useUILanguage()
  const navigate = useNavigate()
  const { roles } = useAuth()
  const canEdit = roles.some((r) => FINANCE.includes(r))
  const [rows, setRows] = useState<AccountRow[] | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [q, setQ] = useState("")
  const [queue, setQueue] = useState<Queue>("all")
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [month, setMonth] = useState(lastMonth)
  const [err, setErr] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [setup, setSetup] = useState(false)

  const load = useCallback(() => {
    call<{ accounts: AccountRow[]; summary?: Summary }>("kamra.receivables.ar_accounts", {
      property: getCurrentProperty(),
    })
      .then((r) => { setRows(r.accounts); setSummary(r.summary ?? null) })
      .catch((e) => setErr(serverError(e)))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (rows ?? []).filter((r) => QUEUES[queue].test(r) &&
      (!s || [r.company_name, r.company, r.account_number, r.contact_name, r.contact_email]
        .some((v) => (v ?? "").toLowerCase().includes(s))))
  }, [rows, q, queue])

  const tally = (k: Queue) => {
    const list = (rows ?? []).filter(QUEUES[k].test)
    const amount = k === "unbilled" ? list.reduce((a, r) => a + (r.unbilled ?? 0), 0)
      : k === "ahead" ? list.reduce((a, r) => a + r.unapplied_credit, 0)
      : k === "overdue" ? list.reduce((a, r) => a + r.overdue, 0)
      : list.reduce((a, r) => a + r.balance, 0)
    return { n: list.length, amount }
  }

  const toggle = (name: string) => setPicked((cur) => {
    const next = new Set(cur)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    return next
  })
  // only what is on screen: a search narrows the selection too
  const chosen = shown.filter((r) => picked.has(r.name))
  const allShown = shown.length > 0 && chosen.length === shown.length

  const sendBulk = async (kind: "statement" | "monthly") => {
    const what = kind === "monthly" ? translate("{m} bills", { m: month }) : translate("statements")
    if (!window.confirm(translate("Email {what} to {n} companies?", { what, n: chosen.length }))) return
    setBusy(true)
    setErr(null)
    try {
      const out = await call<{ queued: number; skipped: string[] }>("kamra.statements.email_statements_bulk", {
        property: getCurrentProperty(), accounts: JSON.stringify(chosen.map((r) => r.name)),
        kind, month: kind === "monthly" ? month : undefined, lang: language,
      })
      setNotice(translate("Sending {what} to {n} companies. Each one is in the Activity log.", { what, n: out.queued })
        + (out.skipped.length ? " " + translate("Not sent, no billing email: {v0}", { v0: out.skipped.join(", ") }) : ""))
      setPicked(new Set())
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const money = (v?: number) => (v ? fmtMoney(v) : "-")
  const late = (v?: number) => <span className={v ? "text-rose-700" : ""}>{money(v)}</span>

  return (
    <div className="w-full space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
          <h1 className="text-2xl font-semibold">{translate("Receivables")}</h1>
          <p className="text-sm text-zinc-500">
            {translate("Company accounts billed on credit")}
            {summary ? ` · ${translate("{v0} received this month", { v0: fmtMoney(summary.received_this_month) })}` : ""}
            {summary?.deposits_held ? ` · ${translate("{v0} advances held", { v0: fmtMoney(summary.deposits_held) })}` : ""}
          </p>
        </div>
        {canEdit ? (
          <Button onClick={() => setSetup(true)}>
            <Plus className="size-4" />{translate("New account")}
          </Button>
        ) : null}
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {notice ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{notice}</p> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" role="group" aria-label={translate("Show")}>
        {(Object.keys(QUEUES) as Queue[]).map((k) => {
          const { n, amount } = tally(k)
          const on = queue === k
          const alarm = (k === "overdue" || k === "over_limit") && n > 0
          return (
            <button key={k} type="button" aria-pressed={on} onClick={() => { setQueue(k); setPicked(new Set()) }}
              className={`rounded-xl border px-3 py-2 text-start transition ${on
                ? alarm ? "border-rose-600 bg-rose-50 ring-1 ring-rose-600" : "border-brand-600 bg-brand-50 ring-1 ring-brand-600"
                : "border-zinc-200 bg-white hover:border-zinc-300"}`}>
              <div className={`text-xs ${alarm ? "font-medium text-rose-800" : "text-zinc-500"}`}>
                {translate(QUEUES[k].label)} · {n}
              </div>
              <div className={`text-lg font-semibold tabular-nums ${alarm ? "text-rose-700" : ""}`}>{fmtMoney(amount)}</div>
            </button>
          )
        })}
      </div>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-3">
          <input
            className="w-full max-w-xs rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
            aria-label={translate("Search company, account no. or contact")}
            placeholder={translate("Search company, account no. or contact")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {canEdit && shown.length ? (
            <Button variant="ghost" onClick={() => setPicked(allShown ? new Set() : new Set(shown.map((r) => r.name)))}>
              {allShown ? translate("Clear selection") : translate("Select all {n}", { n: shown.length })}
            </Button>
          ) : null}
        </CardHeader>
        {chosen.length ? (
          <div className="mx-4 mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 bg-brand-50 px-3 py-2 text-sm">
            <span className="font-medium text-brand-700">
              {translate("{n} selected · {v0} owed", { n: chosen.length, v0: fmtMoney(chosen.reduce((a, r) => a + r.balance, 0)) })}
            </span>
            <span className="flex-1" />
            <Button variant="outline" disabled={busy} onClick={() => void sendBulk("statement")}>{translate("Email statements")}</Button>
            <span className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white ps-2">
              <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
                aria-label={translate("Month")} className="bg-transparent text-sm outline-none" />
              <Button variant="ghost" disabled={busy || !month} onClick={() => void sendBulk("monthly")}>{translate("Send month-end bills")}</Button>
            </span>
            <Button variant="outline" onClick={() => downloadCsv("receivables-selected",
              [translate("Account"), translate("Company"), translate("Contact email"), translate("Not due"), "1-30", "31-60", "61-90", "90+", translate("Balance")],
              chosen.map((r) => [r.account_number ?? "", r.company_name, r.contact_email ?? "", r.not_due ?? 0, r.d1_30 ?? 0,
                r.d31_60 ?? 0, r.d61_90 ?? 0, r.d90p ?? 0, r.balance]))}>
              {translate("Export selected")}
            </Button>
          </div>
        ) : null}
        <CardContent>
          {!rows ? <p className="py-8 text-center text-sm text-zinc-400">{translate("Loading…")}</p> : (
          <DataTable<AccountRow>
            id="receivables.accounts.v2" exportName="receivables" rows={shown} rowKey={(r) => r.name}
            onRowClick={(r) => navigate(`/receivables/${encodeURIComponent(r.name)}`)}
            empty={rows.length ? translate("No account matches.") : translate("No company accounts yet. Open one, or check out a stay billed to a company on credit.")}
            columns={[
              ...(canEdit ? [{ key: "pick", label: "", noSort: true, render: (r: AccountRow) => (
                <input type="checkbox" checked={picked.has(r.name)} aria-label={translate("Select {v0}", { v0: r.company_name })}
                  onClick={(e) => e.stopPropagation()} onChange={() => toggle(r.name)} />) }] : []),
              { key: "company_name", label: translate("Company"), render: (r) => (<div className="text-start">
                <Link className="font-medium hover:underline" to={`/receivables/${encodeURIComponent(r.name)}`}
                  onClick={(e) => e.stopPropagation()}>{r.company_name}</Link>
                {r.restricted ? <span className="ms-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">{translate("Restricted")}</span> : null}
                {overLimit(r) ? <span className="ms-2 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">{translate("Over limit")}</span> : null}
                <span className="block font-mono text-[11px] text-zinc-400">{[r.account_number, r.contact_name].filter(Boolean).join(" · ")}</span>
              </div>) },
              { key: "account_number", label: translate("Account"), hidden: true },
              { key: "contact_email", label: translate("Contact email"), hidden: true },
              { key: "credit_days", label: translate("Terms"), render: (r) => <span className="text-xs text-zinc-500">{translate("{n} days", { n: r.credit_days ?? 0 })}</span> },
              { key: "credit_limit", label: translate("Credit limit"), align: "right", hidden: true, render: (r) => money(r.credit_limit) },
              { key: "unbilled", label: translate("In house, not billed"), align: "right", hidden: true, render: (r) => money(r.unbilled) },
              { key: "not_due", label: translate("Not due"), align: "right", render: (r) => money(r.not_due) },
              { key: "d1_30", label: translate("1 to 30 late"), align: "right", render: (r) => late(r.d1_30) },
              { key: "d31_60", label: translate("31 to 60"), align: "right", render: (r) => late(r.d31_60) },
              { key: "d61_90", label: translate("61 to 90"), align: "right", render: (r) => late(r.d61_90) },
              { key: "d90p", label: "90+", align: "right", render: (r) => late(r.d90p) },
              { key: "balance", label: translate("Balance"), align: "right", render: (r) => <span className="font-medium">{fmtMoney(r.balance)}</span> },
              { key: "last_payment_date", label: translate("Last paid"), align: "right", render: (r) => r.last_payment_date ? (
                <span className="text-xs text-zinc-500">{fmtMoney(r.last_payment ?? 0)}<span className="block">{r.last_payment_date}</span></span>) : "-" },
            ]}
          />
          )}
        </CardContent>
      </Card>

      {setup ? (
        <AccountSetup
          onClose={() => setSetup(false)}
          onSaved={(name) => navigate(`/receivables/${encodeURIComponent(name)}`)}
        />
      ) : null}
    </div>
  )
}

/** Last month as YYYY-MM: the month-end bill goes out after the month closes. */
function lastMonth() {
  const d = new Date()
  d.setDate(0)
  return d.toLocaleDateString("en-CA").slice(0, 7)
}

// ── one account ─────────────────────────────────────────────────────────────

function AccountPage({ account }: { account: string }) {
  const language = useUILanguage()
  const { roles } = useAuth()
  const isFinance = roles.some((r) => FINANCE.includes(r))
  const [acc, setAcc] = useState<Account | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [month, setMonth] = useState(lastMonth)
  const [preview, setPreview] = useState<null | "statement" | "monthly">(null)
  const [tab, setTab] = useState<"open" | "bills" | "payments" | "history">("open")
  const [sheet, setSheet] = useState<
    null | "setup" | "invoice" | "payment" | { view: string } | { transfer: OpenItem } | { action: Action }
  >(null)

  const [history, setHistory] = useState<HistoryRow[]>([])
  const load = useCallback(() => {
    call<Account>("kamra.ledger.city_ledger_account", { account })
      .then(setAcc)
      .catch((e) => setErr(serverError(e)))
    call<{ entries: HistoryRow[] }>("kamra.ledger.city_ledger_history", { account })
      .then((r) => setHistory(r.entries))
      .catch(() => setHistory([]))
  }, [account])
  useEffect(load, [load])

  const done = (msg: string) => {
    setSheet(null)
    setNotice(msg)
    load()
  }

  const emailMonthly = async (): Promise<boolean> => {
    try {
      const res = await call<{ sent_to: string[]; number: string }>("kamra.statements.email_monthly_bill", {
        account, month, lang: language,
      })
      setNotice(translate("{v0} sent to {v1}", { v0: res.number, v1: res.sent_to.join(", ") }))
      return true
    } catch (e) {
      setErr(serverError(e))
      return false
    }
  }

  const emailStatement = async (): Promise<boolean> => {
    try {
      const res = await call<{ sent_to: string[] }>("kamra.statements.email_company_statement", {
        account, lang: language,
      })
      setNotice(translate("Statement sent to {v0}", { v0: res.sent_to.join(", ") }))
      return true
    } catch (e) {
      setErr(serverError(e))
      return false
    }
  }

  if (!acc) {
    return (
      <div className="space-y-3">
        <BackLink />
        {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : <p className="text-sm text-zinc-400">{translate("Loading account…")}</p>}
      </div>
    )
  }

  return (
    <div className="w-full space-y-5">
      <BackLink />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-zinc-400">{acc.account_number}</p>
          <h1 className="text-2xl font-semibold">{acc.company}</h1>
          <p className="text-sm text-zinc-500">
            {translate("Due {n} days after the invoice date", { n: acc.credit_days ?? 0 })}
            {acc.credit_limit > 0
              ? translate(" · Credit limit {v0}", { v0: fmtMoney(acc.credit_limit) })
              : translate(" · No credit limit")}
          </p>
          {acc.billing_address ? (
            <p className="mt-1 whitespace-pre-line text-xs text-zinc-500">{acc.billing_address}</p>
          ) : null}
        </div>
        {isFinance ? (
          <div className="flex flex-wrap items-start gap-2">
            <Button variant="outline" disabled={acc.restricted} onClick={() => setSheet("invoice")}>
              <Plus className="size-4" />{translate("New invoice")}
            </Button>
            <Button onClick={() => setSheet("payment")}>{translate("Record payment")}</Button>
            <details className="relative">
              <summary className="inline-flex h-9 cursor-pointer list-none items-center gap-1 rounded-lg border border-zinc-300 bg-white px-3 text-sm font-medium hover:bg-zinc-50">
                {translate("More")}<ChevronDown className="size-4" aria-hidden />
              </summary>
              <div className="absolute end-0 z-20 mt-1 w-56 rounded-lg border border-zinc-200 bg-white p-1 shadow-lg">
                {([
                  [translate("Statement"), () => setPreview("statement")],
                  [translate("Month-end bill"), () => setPreview("monthly")],
                  [translate("Account setup"), () => setSheet("setup")],
                ] as const).map(([label, fn]) => (
                  <button key={label} type="button"
                    className="block w-full rounded-md px-3 py-2 text-start text-sm hover:bg-zinc-100"
                    onClick={(e) => { (e.currentTarget.closest("details") as HTMLDetailsElement).open = false; fn() }}>
                    {label}
                  </button>
                ))}
              </div>
            </details>
          </div>
        ) : null}
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {notice ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{notice}</p> : null}
      {acc.restricted ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          {translate("Restricted: no new bills go on this account.")}
          {acc.restricted_reason ? ` ${acc.restricted_reason}` : ""}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label={translate("Balance")} value={fmtMoney(acc.balance)} />
        {/* billed: invoices on the account; unbilled: stays in house still running on the company's folio */}
        <Stat label={translate("Billed, unpaid")} value={fmtMoney(acc.open_balance)} />
        <Stat label={translate("In house, not billed")} value={fmtMoney(acc.in_house)} />
        <Stat label={translate("Overdue")} value={fmtMoney(acc.overdue)} tone={acc.overdue > 0 ? "text-rose-700" : undefined} />
        <Stat label={translate("Credit available")}
          value={acc.available_credit == null ? translate("No limit") : fmtMoney(acc.available_credit)}
          tone={acc.available_credit != null && acc.available_credit < 0 ? "text-rose-700" : undefined}
        />
      </div>
      {acc.unapplied_credit > 0 ? (
        <p className="-mt-2 text-xs text-zinc-500">
          {translate("{v0} paid ahead settles the next bill.", { v0: fmtMoney(acc.unapplied_credit) })}
        </p>
      ) : null}

      <AgingBar acc={acc} />

      <div role="tablist" aria-label={translate("Account activity")}
        className="inline-flex flex-wrap rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 text-sm">
        {([
          ["open", translate("Open bills · {n}", { n: acc.open_items.length })],
          ["bills", translate("All bills")],
          ["payments", translate("Payments")],
          ["history", translate("Account history")],
        ] as const).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`rounded-md px-3 py-1.5 ${tab === k ? "bg-white font-medium shadow-sm" : "text-zinc-600 hover:text-zinc-900"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "open" || tab === "bills" ? (
      <Card>
        <CardContent className="pt-4">
          <DataTable<OpenItem>
            id="receivables.invoices" exportName={`${tab === "open" ? "open-bills" : "bills"}-${acc.company}`}
            rows={(tab === "open" ? acc.open_items : (acc.bills ?? acc.open_items)).slice().reverse()} rowKey={(it) => it.folio}
            onRowClick={(it) => setSheet({ view: it.folio })}
            empty={translate("No invoices yet.")}
            columns={[
              { key: "invoice_number", label: translate("Invoice"), value: (it) => it.invoice_number || it.folio,
                render: (it) => <span className="font-mono text-xs">{it.invoice_number || it.folio}</span> },
              { key: "guest_name", label: translate("For"), render: (it) => it.folio_type === "Account"
                ? <span className="text-zinc-500">{translate("Direct invoice")}</span>
                : <>{it.guest_name || "-"}{it.reservation ? <span className="block font-mono text-[11px] text-zinc-400">{it.reservation}</span> : null}</> },
              { key: "invoice_date", label: translate("Billed on") },
              { key: "due_date", label: translate("Due"), render: (it) => it.days_overdue ? (
                <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${it.days_overdue > 30 ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800"}`}>
                  {translate("{n} days late", { n: it.days_overdue })}</span>
              ) : <span>{it.due_date || "-"}</span> },
              { key: "billed", label: translate("Debit"), align: "right", render: (it) => fmtMoney(it.billed) },
              { key: "paid", label: translate("Credit"), align: "right", render: (it) => it.paid ? fmtMoney(it.paid) : "-" },
              { key: "outstanding", label: translate("Total Balance"), align: "right", render: (it) => it.outstanding > 0.005
                ? <span className="font-medium">{fmtMoney(it.outstanding)}</span>
                : <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">{translate("Paid")}</span> },
              { key: "actions", label: "", noSort: true, align: "right", render: (it) => (
                <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                  <Button variant="outline" onClick={() => setSheet({ view: it.folio })}>{translate("View")}</Button>
                  {isFinance ? (
                    <>
                      {it.outstanding > 0.005 ? (
                        <Button variant="outline" onClick={() => setSheet({ transfer: it })}>{translate("Transfer")}</Button>
                      ) : null}
                      <Button variant="outline" onClick={() => setSheet({ action: { kind: "dispute", item: it } })}>
                        {it.disputed ? translate("Clear dispute") : translate("Dispute")}
                      </Button>
                    </>
                  ) : null}
                </div>) },
            ]}
          />
        </CardContent>
      </Card>
      ) : null}

      {acc.pending_payments?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{translate("Payments to confirm")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-xs text-zinc-500">{translate("Recorded by an AI agent. They change nothing on the account until Finance confirms them with a PIN.")}</p>
            <ul className="divide-y divide-zinc-100 text-sm">
              {acc.pending_payments.map((r) => (
                <li key={r.name} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span>
                    <b className="tabular-nums">{fmtMoney(r.amount)}</b> · {translate(r.mode || "Bank Transfer")}
                    {r.reference ? ` · ${r.reference}` : ""}
                    <span className="block text-xs text-zinc-500">
                      {translate("Received {v0}, recorded by {v1}", { v0: r.received_on || "-", v1: r.requested_by })}
                      {r.channel ? ` (${r.channel})` : ""}
                    </span>
                  </span>
                  {isFinance ? (
                    <span className="flex gap-1.5">
                      <Button variant="outline" onClick={() => setSheet({ action: { kind: "reject", request: r } })}>{translate("Reject")}</Button>
                      <Button onClick={() => setSheet({ action: { kind: "confirm", request: r } })}>{translate("Confirm")}</Button>
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {tab === "payments" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{translate("Recent payments")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-zinc-100 text-sm">
              {acc.payments.map((p) => (
                <li key={p.name} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span>
                    {p.posting_date} · {p.reference || "-"}
                    {p.received_on && p.received_on !== p.posting_date
                      ? <span className="ml-1 text-xs text-zinc-500">({translate("received {v0}", { v0: p.received_on })})</span>
                      : null}
                    {p.reversed ? <span className="ml-2 rounded bg-zinc-100 px-1.5 text-[11px] text-zinc-600">{translate("Reversed")}</span> : null}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className={`tabular-nums ${p.reverses ? "text-rose-700" : ""}`}>
                      {fmtMoney(p.reverses ? -(p.debit ?? 0) : p.credit)}
                    </span>
                    {isFinance && !p.reverses && !p.reversed && p.credit > 0 ? (
                      <Button variant="outline" onClick={() => setSheet({ action: { kind: "reverse", payment: p } })}>{translate("Reverse")}</Button>
                    ) : null}
                  </span>
                </li>
              ))}
              {!acc.payments?.length ? <li className="py-6 text-center text-zinc-400">{translate("No payments yet.")}</li> : null}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {/* every bill, credit note and payment on the account, newest first, with the balance after it */}
      {tab === "history" ? (
        <Card>
          <CardContent className="pt-4">
            <DataTable<HistoryRow>
              id="receivables.history" exportName={`account-history-${acc.company}`}
              rows={history.slice().reverse()} rowKey={(h) => h.name}
              empty={translate("Nothing on the account yet.")}
              columns={[
                { key: "posting_date", label: translate("Date"), render: (h) => <span className="whitespace-nowrap">{h.posting_date}</span> },
                { key: "kind", label: translate("Entry"), value: (h) => translate(h.kind), render: (h) => translate(h.kind) },
                { key: "details", label: translate("Details"),
                  value: (h) => [h.invoice_number || h.folio || h.reference || h.notes || "",
                    ...h.applied.map((a) => `${a.invoice_number || a.folio} ${a.amount}`)].join("; "),
                  render: (h) => (<>
                    {h.folio ? (
                      <button type="button" className="hover:underline" onClick={() => setSheet({ view: h.folio! })}>
                        {h.invoice_number || h.folio}{h.guest_name ? ` · ${h.guest_name}` : ""}
                      </button>
                    ) : (h.reference || h.notes || "-")}
                    {/* a payment names the bills it cleared */}
                    {h.applied.map((a) => (
                      <button key={a.folio} type="button" onClick={() => setSheet({ view: a.folio })}
                        className="block text-xs text-zinc-500 hover:underline">
                        {a.invoice_number || a.folio}{a.guest_name ? ` · ${a.guest_name}` : ""} · {fmtMoney(a.amount)}
                      </button>
                    ))}
                  </>) },
                { key: "debit", label: translate("Debit"), align: "right", render: (h) => h.debit ? fmtMoney(h.debit) : "" },
                { key: "credit", label: translate("Credit"), align: "right", render: (h) => h.credit ? fmtMoney(h.credit) : "" },
                { key: "balance", label: translate("Total Balance"), align: "right", render: (h) => <span className="font-medium">{fmtMoney(h.balance)}</span> },
              ]}
            />
          </CardContent>
        </Card>
      ) : null}

      {preview ? (
        <DocumentPreview
          kind={preview} account={account} company={acc.company} lang={language}
          month={month} onMonth={setMonth}
          onClose={() => setPreview(null)}
          onEmail={() => preview === "monthly" ? emailMonthly() : emailStatement()}
        />
      ) : null}
      {sheet === "setup" ? (
        <AccountSetup acc={acc} onClose={() => setSheet(null)} onSaved={() => done(translate("Account saved."))} />
      ) : null}
      {sheet === "payment" ? (
        <CityLedgerPayment account={account} onClose={() => { setSheet(null); load() }} onPosted={load} />
      ) : null}
      {sheet === "invoice" ? (
        <NewInvoice
          acc={acc}
          onClose={() => setSheet(null)}
          onCreated={(inv) => done(translate("Invoice {v0} raised on the account.", { v0: inv }))}
        />
      ) : null}
      {sheet && typeof sheet === "object" && "view" in sheet ? (
        <InvoiceView folio={sheet.view} company={acc.company} onClose={() => setSheet(null)} />
      ) : null}
      {sheet && typeof sheet === "object" && "transfer" in sheet ? (
        <TransferInvoice
          acc={acc}
          item={sheet.transfer}
          onClose={() => setSheet(null)}
          onDone={(to) => done(translate("Bill moved to {v0}.", { v0: to }))}
        />
      ) : null}
      {sheet && typeof sheet === "object" && "action" in sheet ? (
        <AccountAction acc={acc} action={sheet.action} onClose={() => setSheet(null)} onDone={done} />
      ) : null}
    </div>
  )
}

// dispute a bill, reverse a payment, confirm or reject an agent's payment
function AccountAction(props: { acc: Account; action: Action; onClose: () => void; onDone: (msg: string) => void }) {
  useUILanguage()
  const a = props.action
  const [note, setNote] = useState(a.kind === "dispute" ? a.item.dispute_note || "" : "")
  const [code, setCode] = useState("REV-BOUNCE")
  const [codes, setCodes] = useState<{ name: string; description: string }[]>([])
  const [pin, setPin] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const clearing = a.kind === "dispute" && !!a.item.disputed
  const askPin = a.kind === "confirm" || (a.kind === "reverse" && props.acc.cashier_pin_required)

  useEffect(() => {
    if (a.kind !== "reverse") return
    call<{ name: string; description: string }[]>("kamra.ledger.list_reason_codes", { category: "Payment Reversal" })
      .then(setCodes)
      .catch(() => setCodes([]))
  }, [a.kind])

  const title = a.kind === "dispute" ? (clearing ? translate("Clear the dispute") : translate("Dispute this bill"))
    : a.kind === "reverse" ? translate("Reverse payment")
      : a.kind === "confirm" ? translate("Confirm payment") : translate("Reject payment")

  const summary = a.kind === "dispute" ? `${a.item.invoice_number || a.item.folio} · ${fmtMoney(a.item.outstanding)}`
    : a.kind === "reverse" ? `${a.payment.reference || a.payment.name} · ${fmtMoney(a.payment.credit)}`
      : `${fmtMoney(a.request.amount)} · ${translate(a.request.mode || "Bank Transfer")}${a.request.reference ? ` · ${a.request.reference}` : ""}`

  const plan: { folio: string; amount: number }[] =
    a.kind === "confirm" || a.kind === "reject" ? JSON.parse(a.request.allocations || "[]") : []

  const needsNote = (a.kind === "dispute" && !clearing) || a.kind === "reject"
  const ready = !busy && (!needsNote || note.trim()) && (!askPin || pin) && (a.kind !== "reverse" || code)

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      if (a.kind === "dispute") {
        await call("kamra.ledger.set_city_ledger_dispute", {
          account: props.acc.account, folio: a.item.folio, disputed: clearing ? 0 : 1, note: note.trim(),
        })
        props.onDone(clearing ? translate("Dispute cleared.") : translate("Bill marked as disputed. Reminders pause for it."))
      } else if (a.kind === "reverse") {
        const out = await call<{ balance: number }>("kamra.ledger.reverse_city_ledger_payment", {
          payment: a.payment.name, reason_code: code, reason: note.trim() || undefined, pin: pin || undefined,
        })
        props.onDone(translate("Payment reversed. Account balance is now {v0}.", { v0: fmtMoney(out.balance) }))
      } else {
        await call("kamra.ledger.decide_city_ledger_payment", {
          request: a.request.name, approve: a.kind === "confirm" ? 1 : 0, note: note.trim(), pin: pin || undefined,
        })
        props.onDone(a.kind === "confirm" ? translate("Payment confirmed and posted.") : translate("Payment rejected."))
      }
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title={title}
      description={summary}
      onClose={props.onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={props.onClose}>{translate("Cancel")}</Button>
          <Button disabled={!ready} onClick={() => void submit()}>{busy ? translate("Saving…") : title}</Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        {a.kind === "reverse" ? (
          <p className="text-zinc-600">{translate("The bills this payment cleared are owed again, and any credit it left on the account is taken back.")}</p>
        ) : null}
        {a.kind === "dispute" && !clearing ? (
          <p className="text-zinc-600">{translate("A disputed bill stays on the account and in aging. It gets no payment reminders and does not count towards the overdue credit block.")}</p>
        ) : null}
        {plan.length ? (
          <ul className="rounded-lg border border-zinc-200 px-3 py-2">
            {plan.map((row) => (
              <li key={row.folio} className="flex justify-between">
                <span className="font-mono text-xs">{row.folio}</span>
                <span className="tabular-nums">{fmtMoney(row.amount)}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {a.kind === "reverse" ? (
          <label className="block">
            <span className="mb-1 block text-zinc-500">{translate("Reason")}</span>
            <select className={field} value={code} onChange={(e) => setCode(e.target.value)}>
              {(codes.length ? codes : [{ name: "REV-BOUNCE", description: "Cheque bounced" }]).map((c) => (
                <option key={c.name} value={c.name}>{translate(c.description)}</option>
              ))}
            </select>
          </label>
        ) : null}
        {a.kind !== "confirm" && !clearing ? (
          <label className="block">
            <span className="mb-1 block text-zinc-500">{needsNote ? translate("Note") : translate("Note (optional)")}</span>
            <textarea className={field} rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
        ) : null}
        {askPin ? (
          <label className="block">
            <span className="mb-1 block text-zinc-500">{translate("Your cashier PIN")}</span>
            <input type="password" inputMode="numeric" autoComplete="off" className={field}
              value={pin} onChange={(e) => setPin(e.target.value)} />
          </label>
        ) : null}
      </div>
    </Sheet>
  )
}

/** How old what the company owes is: one bar, green to red. */
function AgingBar({ acc }: { acc: Account }) {
  useUILanguage()
  const parts = [
    { k: "Not due", v: acc.not_due, cls: "bg-emerald-600" },
    { k: "1 to 30 late", v: acc.d1_30, cls: "bg-amber-400" },
    { k: "31 to 60 late", v: acc.d31_60, cls: "bg-orange-500" },
    { k: "61 to 90 late", v: acc.d61_90, cls: "bg-rose-500" },
    { k: "90+ late", v: acc.d90p, cls: "bg-rose-800" },
  ]
  const total = parts.reduce((a, p) => a + Math.max(0, p.v), 0)
  if (total < 0.005) return null
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
      <div className="text-xs text-zinc-500">{translate("Age of what is owed")}</div>
      <div className="mt-1.5 flex h-2.5 overflow-hidden rounded-full bg-zinc-100" aria-hidden>
        {parts.map((p) => p.v > 0 ? <div key={p.k} className={p.cls} style={{ width: `${(p.v / total) * 100}%` }} /> : null)}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600">
        {parts.map((p) => (
          <li key={p.k} className="inline-flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${p.cls}`} aria-hidden />
            <b className="tabular-nums text-zinc-800">{fmtMoney(p.v)}</b> {translate(p.k)}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** The statement or month-end bill as the company will get it: a preview,
 *  then print (or Save as PDF from the print dialog) or email. */
function DocumentPreview(props: {
  kind: "statement" | "monthly"; account: string; company: string; lang: string
  month: string; onMonth: (m: string) => void; onClose: () => void; onEmail: () => Promise<boolean>
}) {
  useUILanguage()
  const [html, setHtml] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const frame = useRef<HTMLIFrameElement>(null)
  useEffect(() => {
    let stale = false
    setHtml(null)
    setErr(null)
    if (props.kind === "monthly" && !props.month) return
    call<{ content: string }>(
      props.kind === "monthly" ? "kamra.statements.company_monthly_bill" : "kamra.statements.company_statement",
      { account: props.account, format: "html", lang: props.lang, ...(props.kind === "monthly" ? { month: props.month } : {}) },
    ).then((r) => { if (!stale) setHtml(r.content) }).catch((e) => { if (!stale) setErr(serverError(e)) })
    return () => { stale = true }
  }, [props.kind, props.account, props.lang, props.month])

  return (
    <Sheet
      wide
      title={props.kind === "monthly" ? translate("Month-end bill") : translate("Statement")}
      description={props.company}
      onClose={props.onClose}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" disabled={!html} onClick={() => frame.current?.contentWindow?.print()}>
            <Printer className="size-4" />{translate("Print or save PDF")}
          </Button>
          <Button disabled={!html || busy} onClick={async () => {
            setBusy(true)
            try {
              if (await props.onEmail()) props.onClose()
              else setErr(translate("Not sent. The reason is on the page behind this one."))
            } finally { setBusy(false) }
          }}>
            {busy ? translate("Sending…") : translate("Email to the billing contact")}
          </Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {props.kind === "monthly" ? (
          <label className="flex items-center gap-2 text-zinc-600">
            {translate("Month")}
            <input type="month" value={props.month} onChange={(e) => props.onMonth(e.target.value)}
              className="rounded-lg border border-zinc-300 px-2 py-1" />
          </label>
        ) : null}
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        {!html && !err ? <p className="text-zinc-400">{translate("Loading…")}</p> : null}
        {html ? (
          // sandboxed: no scripts run. Never add allow-scripts while
          // allow-same-origin is set: together they let the page reach the desk
          <iframe ref={frame} title={translate("Preview")} srcDoc={html} sandbox="allow-modals allow-same-origin"
            className="h-[65vh] w-full rounded-lg border border-zinc-200 bg-white" />
        ) : null}
      </div>
    </Sheet>
  )
}

function BackLink() {
  useUILanguage()
  return (
    <Link to="/receivables" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
      <ArrowLeft className="size-4" />{translate("Receivables")}
    </Link>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  useUILanguage()
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  )
}

// ── account setup ───────────────────────────────────────────────────────────

function AccountSetup(props: { acc?: Account; onClose: () => void; onSaved: (account: string) => void }) {
  useUILanguage()
  const a = props.acc
  const [companies, setCompanies] = useState<{ name: string; company_name: string }[]>([])
  const [company, setCompany] = useState(a?.company ?? "")
  const [number, setNumber] = useState(a?.account_number ?? "")
  const [limit, setLimit] = useState(a ? String(a.credit_limit || "") : "")
  const [useDefault, setUseDefault] = useState(a ? a.use_default_credit_days : true)
  const [days, setDays] = useState(a ? String(a.account_credit_days ?? 0) : "30")
  const [address, setAddress] = useState(a?.billing_address ?? "")
  const [restricted, setRestricted] = useState(!!a?.restricted)
  const [reason, setReason] = useState(a?.restricted_reason ?? "")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (a) return
    listResource("Corporate Account", {
      fields: ["name", "company_name"], filters: [["disabled", "=", 0]],
      orderBy: "company_name asc", limit: 500,
    })
      .then((r) => setCompanies(r as unknown as { name: string; company_name: string }[]))
      .catch((e) => setErr(serverError(e)))
  }, [a])

  const save = async () => {
    setBusy(true)
    setErr(null)
    try {
      const out = await call<{ account: string }>("kamra.receivables.save_ar_account", {
        property: getCurrentProperty(),
        company,
        account: a?.account,
        account_number: number.trim() || undefined,
        credit_limit: Number(limit) || 0,
        use_default_credit_days: useDefault ? 1 : 0,
        credit_days: Number(days) || 0,
        billing_address: address.trim() || undefined,
        restricted: restricted ? 1 : 0,
        restricted_reason: restricted ? reason.trim() : undefined,
      })
      props.onSaved(out.account)
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title={a ? translate("Account setup") : translate("New company account")}
      description={a ? a.company : translate("Bill a company on credit")}
      onClose={props.onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={props.onClose}>{translate("Cancel")}</Button>
          <Button disabled={busy || !company || (restricted && !reason.trim())} onClick={() => void save()}>
            {busy ? translate("Saving…") : translate("Save")}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        {!a ? (
          <label className="block">
            <span className="mb-1 block text-zinc-500">{translate("Company")}</span>
            <select className={field} value={company} onChange={(e) => setCompany(e.target.value)} autoFocus>
              <option value="">{translate("Pick a company…")}</option>
              {companies.map((c) => <option key={c.name} value={c.name}>{c.company_name || c.name}</option>)}
            </select>
            <span className="mt-1 block text-xs text-zinc-400">
              {translate("Not listed? Add it under Companies first. Opening an account puts the company on credit.")}
            </span>
          </label>
        ) : null}
        <label className="block">
          <span className="mb-1 block text-zinc-500">{translate("Account number")}</span>
          <input className={field} value={number} maxLength={40} placeholder={translate("Leave blank to number it for you")}
            onChange={(e) => setNumber(e.target.value)} />
        </label>
        <label className="block">
          <span className="mb-1 block text-zinc-500">{translate("Credit limit")}</span>
          <input className={field} type="number" min="0" step="0.01" inputMode="decimal" value={limit}
            placeholder={translate("0 = no limit")} onChange={(e) => setLimit(e.target.value)} />
        </label>
        <div>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useDefault} onChange={(e) => setUseDefault(e.target.checked)} />
            {translate("Use the property's payment terms")}
          </label>
          {!useDefault ? (
            <label className="mt-2 block">
              <span className="mb-1 block text-zinc-500">{translate("Days to pay after the invoice date")}</span>
              <input className={field} type="number" min="0" step="1" value={days} onChange={(e) => setDays(e.target.value)} />
            </label>
          ) : null}
        </div>
        <label className="block">
          <span className="mb-1 block text-zinc-500">{translate("Billing address")}</span>
          <textarea className={field} rows={3} value={address} onChange={(e) => setAddress(e.target.value)} />
        </label>
        <div className="rounded-lg border border-zinc-200 p-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} />
            {translate("Restricted: take no new bills")}
          </label>
          {restricted ? (
            <input className={`${field} mt-2`} value={reason} maxLength={140}
              placeholder={translate("Why (shown to whoever tries to bill it)")}
              onChange={(e) => setReason(e.target.value)} />
          ) : null}
          <p className="mt-1 text-xs text-zinc-400">{translate("Payments and statements keep working while it is restricted.")}</p>
        </div>
      </div>
    </Sheet>
  )
}

// ── new invoice ─────────────────────────────────────────────────────────────

type Line = { charge_type: string; description: string; amount: string; qty: string; gst_rate: number }

function NewInvoice(props: { acc: Account; onClose: () => void; onCreated: (invoice: string) => void }) {
  useUILanguage()
  const loc = useLocale()
  const [codes, setCodes] = useState<Record<string, string>>({})
  const [lines, setLines] = useState<Line[]>([])
  const [reference, setReference] = useState("")
  const [override, setOverride] = useState("")
  const [needsOverride, setNeedsOverride] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    void loadLocale().then((l) =>
      setLines([{ charge_type: "Misc", description: "", amount: "", qty: "1", gst_rate: l.tax_rates[0] ?? 0 }]))
    listResource("Transaction Code", {
      fields: ["code", "description", "charge_type"],
      filters: [["charge_type", "in", BILLABLE.join(",")]], limit: 200, orderBy: "code asc",
    })
      .then((rows) => {
        const m: Record<string, string> = {}
        for (const r of rows) if (!m[String(r.charge_type)]) m[String(r.charge_type)] = `${r.code} · ${r.description}`
        setCodes(m)
      })
      .catch(() => undefined)
  }, [])

  // the server taxes food & beverage at the hotel's rate whatever is picked
  const fnbRate = (l: Line) => {
    const text = `${l.charge_type} ${l.description}`.toLowerCase()
    return loc.fnb_tax_rate != null && (loc.fnb_charge_words ?? []).some((w) => text.includes(w))
      ? Number(loc.fnb_tax_rate) : null
  }
  const rateOf = (l: Line) => fnbRate(l) ?? l.gst_rate
  const net = (l: Line) => Math.round((Number(l.amount) || 0) * (Number(l.qty) || 0) * 100) / 100
  const subtotal = lines.reduce((s, l) => s + net(l), 0)
  const tax = lines.reduce((s, l) => s + Math.round(net(l) * rateOf(l)) / 100, 0)

  const set = (i: number, patch: Partial<Line>) =>
    setLines((cur) => cur.map((l, j) => (j === i ? { ...l, ...patch } : l)))

  const problem = !lines.length ? "Add a line."
    : lines.some((l) => !l.description.trim()) ? "Every line needs a description."
    : lines.some((l) => !(Number(l.amount) > 0)) ? "Every line needs a price above zero."
    : lines.some((l) => !(Number(l.qty) >= 1) || !Number.isInteger(Number(l.qty))) ? "Quantity is a whole number, 1 or more."
    : null

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      const out = await call<{ invoice_number: string; credit?: { warning?: string } }>(
        "kamra.receivables.create_ar_invoice", {
          account: props.acc.account,
          lines: JSON.stringify(lines.map((l) => ({
            charge_type: l.charge_type, description: l.description.trim(),
            amount: Number(l.amount), qty: Number(l.qty), gst_rate: rateOf(l),
          }))),
          reference: reference.trim() || undefined,
          credit_override_reason: override.trim() || undefined,
        })
      props.onCreated(out.invoice_number)
    } catch (e) {
      const msg = serverError(e)
      if (/credit control blocks/i.test(msg)) setNeedsOverride(true)
      setErr(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      wide
      title={translate("New invoice")}
      description={`${props.acc.company} · ${props.acc.account_number ?? ""}`}
      onClose={props.onClose}
      footer={
        <div className="flex items-center justify-between gap-2">
          <p className={`text-sm ${problem ? "text-zinc-400" : "text-zinc-600"}`}>
            {problem ? translate(problem) : translate("Due {n} days after today's business date.", { n: props.acc.credit_days ?? 0 })}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={props.onClose}>{translate("Cancel")}</Button>
            <Button disabled={busy || !!problem || (needsOverride && !override.trim())} onClick={() => void submit()}>
              {busy ? translate("Raising…") : translate("Raise invoice for {v0}", { v0: fmtMoney(subtotal + tax) })}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        {needsOverride ? (
          <label className="block rounded-lg border border-amber-200 bg-amber-50 p-3">
            <span className="mb-1 block text-amber-900">{translate("Override credit control - say why (it is logged)")}</span>
            <input className={field} value={override} maxLength={140} onChange={(e) => setOverride(e.target.value)} />
          </label>
        ) : null}

        <label className="block max-w-md">
          <span className="mb-1 block text-zinc-500">{translate("Reference (PO number, event, contract)")}</span>
          <input className={field} value={reference} maxLength={140} onChange={(e) => setReference(e.target.value)} />
        </label>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-2">{translate("Charge")}</th>
                <th className="py-2 pr-2">{translate("Description")}</th>
                <th className="w-28 py-2 pr-2 text-right">{translate("Price")}</th>
                <th className="w-16 py-2 pr-2 text-right">{translate("Qty")}</th>
                <th className="w-24 py-2 pr-2">{taxLabel()}</th>
                <th className="w-28 py-2 pr-2 text-right">{translate("Total")}</th>
                <th className="w-8 py-2" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => {
                const fnb = fnbRate(l)
                return (
                  <tr key={i} className="border-t border-zinc-100 align-top">
                    <td className="py-2 pr-2">
                      <select className={field} value={l.charge_type} onChange={(e) => set(i, { charge_type: e.target.value })}>
                        {BILLABLE.map((c) => <option key={c} value={c}>{codes[c] ?? translate(c)}</option>)}
                      </select>
                    </td>
                    <td className="py-2 pr-2">
                      <input className={field} value={l.description} maxLength={140}
                        onChange={(e) => set(i, { description: e.target.value })} />
                    </td>
                    <td className="py-2 pr-2">
                      <input className={`${field} text-right`} type="number" min="0" step="0.01" inputMode="decimal"
                        value={l.amount} onChange={(e) => set(i, { amount: e.target.value })} />
                    </td>
                    <td className="py-2 pr-2">
                      <input className={`${field} text-right`} type="number" min="1" step="1"
                        value={l.qty} onChange={(e) => set(i, { qty: e.target.value })} />
                    </td>
                    <td className="py-2 pr-2">
                      <select className={field} value={fnb ?? l.gst_rate} disabled={fnb != null}
                        title={fnb != null ? translate("Food & beverage is taxed at the hotel's F&B rate") : undefined}
                        onChange={(e) => set(i, { gst_rate: Number(e.target.value) })}>
                        {Array.from(new Set([...loc.tax_rates, ...(fnb != null ? [fnb] : [])])).map((r) =>
                          <option key={r} value={r}>{r}%</option>)}
                      </select>
                    </td>
                    <td className="py-2 pr-2 pt-3.5 text-right tabular-nums">
                      {fmtMoney(net(l) + Math.round(net(l) * rateOf(l)) / 100)}
                    </td>
                    <td className="py-2">
                      <Button variant="ghost" aria-label={translate("Remove line")} disabled={lines.length === 1}
                        onClick={() => setLines((cur) => cur.filter((_, j) => j !== i))}>×</Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <Button variant="outline" onClick={() =>
          setLines((cur) => [...cur, { charge_type: "Misc", description: "", amount: "", qty: "1", gst_rate: cur[cur.length - 1]?.gst_rate ?? 0 }])}>
          <Plus className="size-4" />{translate("Add line")}
        </Button>

        <dl className="ml-auto max-w-xs space-y-1">
          <div className="flex justify-between"><dt className="text-zinc-500">{translate("Subtotal")}</dt><dd className="tabular-nums">{fmtMoney(subtotal)}</dd></div>
          <div className="flex justify-between"><dt className="text-zinc-500">{taxLabel()}</dt><dd className="tabular-nums">{fmtMoney(tax)}</dd></div>
          <div className="flex justify-between border-t border-zinc-200 pt-1 font-semibold"><dt>{translate("Invoice total")}</dt><dd className="tabular-nums">{fmtMoney(subtotal + tax)}</dd></div>
        </dl>
      </div>
    </Sheet>
  )
}

// ── one bill ────────────────────────────────────────────────────────────────

type Invoice = {
  folio: string
  folio_type: string
  reservation?: string | null
  guest_name?: string | null
  invoice_number?: string | null
  closed_on?: string | null
  charges_total: number
  tax_total: number
  grand_total: number
  lines: { posting_date: string; transaction_code?: string; description: string; qty: number; rate: number; amount: number; gst_rate: number; total: number }[]
}

function InvoiceView(props: { folio: string; company: string; onClose: () => void }) {
  useUILanguage()
  const [inv, setInv] = useState<Invoice | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    call<Invoice>("kamra.receivables.ar_invoice", { folio: props.folio })
      .then(setInv)
      .catch((e) => setErr(serverError(e)))
  }, [props.folio])

  return (
    <Sheet
      wide
      title={inv?.invoice_number ? translate("Invoice {v0}", { v0: inv.invoice_number }) : translate("Bill")}
      description={props.company}
      onClose={props.onClose}
      footer={
        <div className="flex justify-end gap-2">
          {inv?.reservation ? (
            <Link to={`/billing/${encodeURIComponent(inv.folio)}`}>
              <Button variant="outline">{translate("Open the stay's bill")}</Button>
            </Link>
          ) : inv ? (
            // the account invoice prints on the same tax invoice as any folio
            <Link to={`/billing/${encodeURIComponent(inv.folio)}`}>
              <Button variant="outline"><Printer className="size-4" />{translate("Print invoice")}</Button>
            </Link>
          ) : null}
          <Button onClick={props.onClose}>{translate("Close")}</Button>
        </div>
      }
    >
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {!inv ? <p className="text-sm text-zinc-400">{translate("Loading…")}</p> : (
        <div className="space-y-4 text-sm">
          <p className="text-zinc-500">
            {inv.folio_type === "Account" ? translate("Raised on the account") : (inv.guest_name || "")}
            {inv.reservation ? ` · ${inv.reservation}` : ""}
            {inv.closed_on ? ` · ${inv.closed_on.slice(0, 10)}` : ""}
          </p>
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Date")}</th>
                <th className="py-2 pr-3">{translate("Description")}</th>
                <th className="py-2 pr-3 text-right">{translate("Qty")}</th>
                <th className="py-2 pr-3 text-right">{translate("Amount")}</th>
                <th className="py-2 pr-3 text-right">{taxLabel()}</th>
                <th className="py-2 text-right">{translate("Total")}</th>
              </tr>
            </thead>
            <tbody>
              {inv.lines.map((l, i) => (
                <tr key={i} className="border-t border-zinc-100">
                  <td className="py-2 pr-3">{l.posting_date}</td>
                  <td className="py-2 pr-3">
                    {l.transaction_code ? <span className="mr-1.5 font-mono text-xs text-zinc-400">{l.transaction_code}</span> : null}
                    {l.description}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{l.qty}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtMoney(l.amount)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{l.gst_rate}%</td>
                  <td className="py-2 text-right tabular-nums">{fmtMoney(l.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="ml-auto max-w-xs space-y-1">
            <div className="flex justify-between"><dt className="text-zinc-500">{translate("Subtotal")}</dt><dd className="tabular-nums">{fmtMoney(inv.charges_total)}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">{taxLabel()}</dt><dd className="tabular-nums">{fmtMoney(inv.tax_total)}</dd></div>
            <div className="flex justify-between border-t border-zinc-200 pt-1 font-semibold"><dt>{translate("Total")}</dt><dd className="tabular-nums">{fmtMoney(inv.grand_total)}</dd></div>
          </dl>
        </div>
      )}
    </Sheet>
  )
}

// ── move a bill to another account ──────────────────────────────────────────

function TransferInvoice(props: { acc: Account; item: OpenItem; onClose: () => void; onDone: (to: string) => void }) {
  useUILanguage()
  const [accounts, setAccounts] = useState<AccountRow[]>([])
  const [to, setTo] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    call<{ accounts: AccountRow[] }>("kamra.receivables.ar_accounts", { property: getCurrentProperty() })
      .then((r) => setAccounts(r.accounts.filter((a) => a.name !== props.acc.account && !a.restricted)))
      .catch((e) => setErr(serverError(e)))
  }, [props.acc.account])

  const target = accounts.find((a) => a.name === to)
  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      await call("kamra.receivables.transfer_ar_invoice", {
        account: props.acc.account, folio: props.item.folio, to_account: to,
        reason: reason.trim() || undefined,
      })
      props.onDone(target?.company_name ?? to)
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      title={translate("Transfer a bill")}
      description={`${props.item.invoice_number || props.item.folio} · ${fmtMoney(props.item.outstanding)}`}
      onClose={props.onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={props.onClose}>{translate("Cancel")}</Button>
          <Button disabled={busy || !to} onClick={() => void submit()}>
            {busy ? translate("Moving…") : translate("Move {v0}", { v0: fmtMoney(props.item.outstanding) })}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        <p className="text-zinc-600">
          {translate("What is still owed moves to the other company's account. What {v0} already paid stays here. The bill keeps its number and date, so it ages from when it was raised.", { v0: props.acc.company })}
        </p>
        <label className="block">
          <span className="mb-1 block text-zinc-500">{translate("Bill to")}</span>
          <select className={field} value={to} onChange={(e) => setTo(e.target.value)} autoFocus>
            <option value="">{translate("Pick an account…")}</option>
            {accounts.map((a) => (
              <option key={a.name} value={a.name}>{a.company_name}{a.account_number ? ` · ${a.account_number}` : ""}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-zinc-500">{translate("Note (optional)")}</span>
          <input className={field} value={reason} maxLength={140} onChange={(e) => setReason(e.target.value)} />
        </label>
      </div>
    </Sheet>
  )
}
