import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Plus } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { listResource, serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import { fmtMoney, loadLocale, taxLabel, useLocale } from "../lib/money"
import { useAuth } from "../lib/auth"
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
}

type Account = {
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
  open_items: OpenItem[]
  payments: { name: string; posting_date: string; credit: number; reference?: string }[]
}

const field = "w-full rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"

export default function Receivables() {
  const { account } = useParams()
  return account ? <AccountPage account={account} /> : <AccountList />
}

// ── list ────────────────────────────────────────────────────────────────────

function AccountList() {
  useUILanguage()
  const navigate = useNavigate()
  const { roles } = useAuth()
  const canEdit = roles.some((r) => FINANCE.includes(r))
  const [rows, setRows] = useState<AccountRow[] | null>(null)
  const [q, setQ] = useState("")
  const [owing, setOwing] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [setup, setSetup] = useState(false)

  const load = useCallback(() => {
    call<{ accounts: AccountRow[] }>("kamra.receivables.ar_accounts", {
      property: getCurrentProperty(),
    })
      .then((r) => setRows(r.accounts))
      .catch((e) => setErr(serverError(e)))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (rows ?? []).filter((r) =>
      (!owing || r.balance > 0.005) &&
      (!s || [r.company_name, r.company, r.account_number, r.contact_name]
        .some((v) => (v ?? "").toLowerCase().includes(s))))
  }, [rows, q, owing])

  const total = shown.reduce((s, r) => s + Number(r.balance || 0), 0)
  const overdue = shown.reduce((s, r) => s + Number(r.overdue || 0), 0)

  return (
    <div className="w-full space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
          <h1 className="text-2xl font-semibold">{translate("Receivables")}</h1>
          <p className="text-sm text-zinc-500">{translate("Company accounts billed on credit")}</p>
        </div>
        {canEdit ? (
          <Button onClick={() => setSetup(true)}>
            <Plus className="size-4" />{translate("New account")}
          </Button>
        ) : null}
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Owed to the hotel" value={fmtMoney(total)} />
        <Stat label="Overdue" value={fmtMoney(overdue)} tone={overdue > 0 ? "text-rose-700" : undefined} />
        <Stat label="Accounts" value={String(shown.length)} />
      </div>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-3">
          <input
            className="w-full max-w-xs rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
            placeholder={translate("Search company, account no. or contact")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <label className="flex items-center gap-1.5 text-sm text-zinc-600">
            <input type="checkbox" checked={owing} onChange={(e) => setOwing(e.target.checked)} />
            {translate("Only accounts that owe")}
          </label>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Account")}</th>
                <th className="py-2 pr-3">{translate("Company")}</th>
                <th className="py-2 pr-3">{translate("Contact")}</th>
                <th className="py-2 pr-3">{translate("Terms")}</th>
                <th className="py-2 pr-3 text-right">{translate("Credit limit")}</th>
                <th className="py-2 pr-3 text-right">{translate("Overdue")}</th>
                <th className="py-2 text-right">{translate("Balance")}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr
                  key={r.name}
                  className="cursor-pointer border-t border-zinc-100 hover:bg-zinc-50"
                  onClick={() => navigate(`/receivables/${encodeURIComponent(r.name)}`)}
                >
                  <td className="py-2 pr-3 font-mono text-xs">{r.account_number || "-"}</td>
                  <td className="py-2 pr-3">
                    <Link
                      className="font-medium hover:underline"
                      to={`/receivables/${encodeURIComponent(r.name)}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {r.company_name}
                    </Link>
                    {r.restricted ? (
                      <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">{translate("Restricted")}</span>
                    ) : null}
                    {r.credit_limit > 0 && r.balance > r.credit_limit ? (
                      <span className="ml-2 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">{translate("Over limit")}</span>
                    ) : null}
                  </td>
                  <td className="py-2 pr-3 text-zinc-600">
                    {r.contact_name || "-"}
                    {r.contact_email ? <span className="block text-xs text-zinc-400">{r.contact_email}</span> : null}
                  </td>
                  <td className="py-2 pr-3 text-xs text-zinc-500">{translate("{n} days", { n: r.credit_days ?? 0 })}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{r.credit_limit > 0 ? fmtMoney(r.credit_limit) : "-"}</td>
                  <td className={`py-2 pr-3 text-right tabular-nums ${r.overdue ? "font-medium text-rose-700" : ""}`}>
                    {r.overdue ? fmtMoney(r.overdue) : "-"}
                  </td>
                  <td className="py-2 text-right font-medium tabular-nums">{fmtMoney(r.balance)}</td>
                </tr>
              ))}
              {rows && !shown.length ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-zinc-400">
                    {rows.length ? translate("No account matches.") : translate("No company accounts yet. Open one, or check out a stay billed to a company on credit.")}
                  </td>
                </tr>
              ) : null}
              {!rows ? (
                <tr><td colSpan={7} className="py-8 text-center text-zinc-400">{translate("Loading…")}</td></tr>
              ) : null}
            </tbody>
          </table>
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

// ── one account ─────────────────────────────────────────────────────────────

function AccountPage({ account }: { account: string }) {
  const language = useUILanguage()
  const { roles } = useAuth()
  const isFinance = roles.some((r) => FINANCE.includes(r))
  const [acc, setAcc] = useState<Account | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  // last month by default: the month-end bill goes out after the month closes
  const [month, setMonth] = useState(() => {
    const d = new Date()
    d.setDate(0)
    return d.toLocaleDateString("en-CA").slice(0, 7)
  })
  const [sheet, setSheet] = useState<
    null | "setup" | "invoice" | "payment" | { view: string } | { transfer: OpenItem }
  >(null)

  const load = useCallback(() => {
    call<Account>("kamra.ledger.city_ledger_account", { account })
      .then(setAcc)
      .catch((e) => setErr(serverError(e)))
  }, [account])
  useEffect(load, [load])

  const done = (msg: string) => {
    setSheet(null)
    setNotice(msg)
    load()
  }

  // the statement and the month-end bill are HTML pages: the browser
  // prints them or saves them as PDF
  const openPage = async (method: string, args: Record<string, unknown> = {}) => {
    try {
      const res = await call<{ content: string }>(method, {
        account, format: "html", lang: language, ...args,
      })
      const w = window.open("", "_blank")
      if (w) {
        w.document.write(res.content)
        w.document.close()
        w.print()
      }
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const emailMonthly = async () => {
    try {
      const res = await call<{ sent_to: string[]; number: string }>("kamra.statements.email_monthly_bill", {
        account, month, lang: language,
      })
      setNotice(translate("{v0} sent to {v1}", { v0: res.number, v1: res.sent_to.join(", ") }))
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const emailStatement = async () => {
    try {
      const res = await call<{ sent_to: string[] }>("kamra.statements.email_company_statement", {
        account, lang: language,
      })
      setNotice(translate("Statement sent to {v0}", { v0: res.sent_to.join(", ") }))
    } catch (e) {
      setErr(serverError(e))
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
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setSheet("setup")}>{translate("Account setup")}</Button>
            <Button variant="outline" onClick={() => void openPage("kamra.statements.company_statement")}>{translate("Statement")}</Button>
            <Button variant="outline" onClick={() => void emailStatement()}>{translate("Email statement")}</Button>
            <span className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white pl-2">
              <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
                aria-label={translate("Month")} className="bg-transparent text-sm outline-none" />
              <Button variant="ghost" disabled={!month}
                onClick={() => void openPage("kamra.statements.company_monthly_bill", { month })}>{translate("Month-end bill")}</Button>
              <Button variant="ghost" disabled={!month} onClick={() => void emailMonthly()}>{translate("Email")}</Button>
            </span>
            <Button variant="outline" onClick={() => setSheet("payment")}>{translate("Record payment")}</Button>
            <Button disabled={acc.restricted} onClick={() => setSheet("invoice")}>
              <Plus className="size-4" />{translate("New invoice")}
            </Button>
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

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Balance" value={fmtMoney(acc.balance)} />
        <Stat label="Open bills" value={fmtMoney(acc.open_balance)} />
        <Stat label="Overdue" value={fmtMoney(acc.overdue)} tone={acc.overdue > 0 ? "text-rose-700" : undefined} />
        <Stat
          label="Credit available"
          value={acc.available_credit == null ? translate("No limit") : fmtMoney(acc.available_credit)}
          tone={acc.available_credit != null && acc.available_credit < 0 ? "text-rose-700" : undefined}
        />
      </div>
      {acc.in_house > 0 || acc.unapplied_credit > 0 ? (
        <p className="-mt-2 text-xs text-zinc-500">
          {acc.in_house > 0 ? translate("{v0} more is running on stays in house and counts against the limit.", { v0: fmtMoney(acc.in_house) }) : ""}
          {acc.in_house > 0 && acc.unapplied_credit > 0 ? " " : ""}
          {acc.unapplied_credit > 0 ? translate("{v0} paid ahead settles the next bill.", { v0: fmtMoney(acc.unapplied_credit) }) : ""}
        </p>
      ) : null}

      <div className="grid grid-cols-5 overflow-hidden rounded-lg border border-zinc-200 bg-white text-center text-xs">
        {([
          ["Not due", acc.not_due],
          ["1 to 30 overdue", acc.d1_30],
          ["31 to 60", acc.d31_60],
          ["61 to 90", acc.d61_90],
          ["90+", acc.d90p],
        ] as const).map(([k, v]) => (
          <div key={k} className="border-r border-zinc-100 px-2 py-2 last:border-r-0">
            <div className="text-zinc-400">{translate(k)}</div>
            <div className="font-medium tabular-nums">{fmtMoney(v)}</div>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{translate("Open bills")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-400">
              <tr>
                <th className="py-2 pr-3">{translate("Invoice")}</th>
                <th className="py-2 pr-3">{translate("For")}</th>
                <th className="py-2 pr-3">{translate("Billed on")}</th>
                <th className="py-2 pr-3">{translate("Due")}</th>
                <th className="py-2 pr-3 text-right">{translate("Billed")}</th>
                <th className="py-2 pr-3 text-right">{translate("Paid")}</th>
                <th className="py-2 pr-3 text-right">{translate("Owed")}</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {acc.open_items.map((it) => (
                <tr key={it.folio} className="border-t border-zinc-100">
                  <td className="py-2 pr-3 font-mono text-xs">{it.invoice_number || it.folio}</td>
                  <td className="py-2 pr-3">
                    {it.folio_type === "Account" ? (
                      <span className="text-zinc-500">{translate("Direct invoice")}</span>
                    ) : (
                      <>
                        {it.guest_name || "-"}
                        {it.reservation ? <span className="block font-mono text-[11px] text-zinc-400">{it.reservation}</span> : null}
                      </>
                    )}
                  </td>
                  <td className="py-2 pr-3">{it.invoice_date}</td>
                  <td className={`py-2 pr-3 ${it.days_overdue ? "text-rose-700" : ""}`}>
                    {it.due_date || "-"}
                    {it.days_overdue ? <span className="ml-1 text-xs">({translate("{n}d late", { n: it.days_overdue })})</span> : null}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtMoney(it.billed)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{it.paid ? fmtMoney(it.paid) : "-"}</td>
                  <td className="py-2 pr-3 text-right font-medium tabular-nums">{fmtMoney(it.outstanding)}</td>
                  <td className="py-2 text-right">
                    <div className="flex justify-end gap-1.5">
                      <Button variant="outline" onClick={() => setSheet({ view: it.folio })}>{translate("View")}</Button>
                      {isFinance ? (
                        <Button variant="outline" onClick={() => setSheet({ transfer: it })}>{translate("Transfer")}</Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
              {!acc.open_items.length ? (
                <tr><td colSpan={8} className="py-8 text-center text-zinc-400">{translate("Nothing owed on this account.")}</td></tr>
              ) : null}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {acc.payments.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{translate("Recent payments")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-zinc-100 text-sm">
              {acc.payments.map((p) => (
                <li key={p.name} className="flex justify-between py-2">
                  <span>{p.posting_date} · {p.reference || "-"}</span>
                  <span className="tabular-nums">{fmtMoney(p.credit)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
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
    </div>
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
      <div className="text-xs text-zinc-400">{translate(label)}</div>
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
