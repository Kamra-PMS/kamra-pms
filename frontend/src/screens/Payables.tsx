import { useCallback, useEffect, useMemo, useState } from "react"
import { Plus } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import { fmtMoney, taxLabel, taxRates, useLocale } from "../lib/money"
import { useAuth } from "../lib/auth"
import { t as translate, useUILanguage } from "../lib/i18n"

// Accounts payable: suppliers and the bills the hotel owes them. Every
// figure (tax, total, still owed, aging) comes from kamra.payables.
// Finance and Hotel Admin enter and pay approved bills; only Hotel Admin approves.

const ENTER = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
const APPROVE = ["Hotel Admin", "System Manager", "Administrator"]

type Bill = {
  name: string
  vendor: string
  vendor_name: string
  bill_number?: string | null
  bill_date: string
  due_date: string
  expense_category: string
  description?: string | null
  amount: number
  tax_rate: number
  tax_amount: number
  total: number
  paid: number
  outstanding: number
  status: string
  days_overdue: number
}

type Vendor = {
  name: string
  vendor_name: string
  expense_category: string
  payment_terms_days: number
  tax_id?: string | null
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  notes?: string | null
  disabled: number
  balance: number
  overdue: number
  open_bills: number
}

type Aging = Record<"not_due" | "d1_30" | "d31_60" | "d61_90" | "d90p" | "overdue" | "balance", number>

const field = "w-full rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
const today = () => new Date().toISOString().slice(0, 10)

export default function Payables() {
  useUILanguage()
  useLocale()
  const { roles } = useAuth()
  const canEnter = roles.some((r) => ENTER.includes(r))
  const canApprove = roles.some((r) => APPROVE.includes(r))
  const [tab, setTab] = useState<"bills" | "vendors">("bills")
  const [status, setStatus] = useState("open")
  const [bills, setBills] = useState<Bill[] | null>(null)
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [aging, setAging] = useState<Aging | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [sheet, setSheet] = useState<
    null | "bill" | { vendor?: Vendor } | { pay: Bill } | { cancel: Bill }
  >(null)

  const load = useCallback(() => {
    const property = getCurrentProperty()
    Promise.all([
      call<{ bills: Bill[] }>("kamra.payables.vendor_bills", { property, status }),
      call<{ vendors: Vendor[]; categories: string[] }>("kamra.payables.vendors", {
        property, include_disabled: 1,
      }),
      call<{ totals: Aging }>("kamra.payables.payables_aging", { property }),
    ])
      .then(([b, v, a]) => {
        setBills(b.bills)
        setVendors(v.vendors)
        setCategories(v.categories)
        setAging(a.totals)
      })
      .catch((e) => setErr(serverError(e)))
  }, [status])
  useEffect(load, [load])

  const done = (msg: string) => {
    setSheet(null)
    setNotice(msg)
    setErr(null)
    load()
  }

  const approve = async (b: Bill) => {
    try {
      await call("kamra.payables.approve_vendor_bill", { bill: b.name })
      done(translate("Bill {v0} approved.", { v0: b.name }))
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const waiting = (bills ?? []).filter((b) => b.status === "Awaiting Approval").length

  return (
    <div className="w-full space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{translate("Books")}</p>
          <h1 className="text-2xl font-semibold">{translate("Payables")}</h1>
          <p className="text-sm text-zinc-500">{translate("Supplier bills the hotel pays later. Cash paid from the till stays in Petty Cash.")}</p>
        </div>
        {canEnter ? (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setSheet({})}>
              <Plus className="size-4" />{translate("New vendor")}
            </Button>
            <Button disabled={!vendors.some((v) => !v.disabled)} onClick={() => setSheet("bill")}>
              <Plus className="size-4" />{translate("New bill")}
            </Button>
          </div>
        ) : null}
      </div>
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      {notice ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{notice}</p> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Owed to suppliers" value={fmtMoney(aging?.balance ?? 0)} />
        <Stat label="Overdue" value={fmtMoney(aging?.overdue ?? 0)} tone={aging?.overdue ? "text-rose-700" : undefined} />
        <Stat label="Awaiting approval" value={String(waiting)} tone={waiting ? "text-amber-700" : undefined} />
      </div>

      {aging ? (
        <div className="grid grid-cols-5 overflow-hidden rounded-lg border border-zinc-200 bg-white text-center text-xs">
          {([
            ["Not due", aging.not_due],
            ["1 to 30 overdue", aging.d1_30],
            ["31 to 60", aging.d31_60],
            ["61 to 90", aging.d61_90],
            ["90+", aging.d90p],
          ] as const).map(([k, v]) => (
            <div key={k} className="border-r border-zinc-100 px-2 py-2 last:border-r-0">
              <div className="text-zinc-400">{translate(k)}</div>
              <div className="font-medium tabular-nums">{fmtMoney(v)}</div>
            </div>
          ))}
        </div>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-3">
          <div className="inline-flex rounded-lg border border-zinc-200 p-0.5 text-sm">
            {(["bills", "vendors"] as const).map((k) => (
              <button
                key={k}
                className={`rounded-md px-3 py-1 ${tab === k ? "bg-zinc-900 text-white" : "text-zinc-600"}`}
                onClick={() => setTab(k)}
              >
                {translate(k === "bills" ? "Bills" : "Vendors")}
              </button>
            ))}
          </div>
          {tab === "bills" ? (
            <select className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="open">{translate("Still to pay")}</option>
              <option value="Awaiting Approval">{translate("Awaiting approval")}</option>
              <option value="Paid">{translate("Paid")}</option>
              <option value="Cancelled">{translate("Cancelled")}</option>
              <option value="all">{translate("All bills")}</option>
            </select>
          ) : null}
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {tab === "bills" ? (
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-400">
                <tr>
                  <th className="py-2 pr-3">{translate("Vendor")}</th>
                  <th className="py-2 pr-3">{translate("Bill")}</th>
                  <th className="py-2 pr-3">{translate("Category")}</th>
                  <th className="py-2 pr-3">{translate("Due")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Total")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Owed")}</th>
                  <th className="py-2 pr-3">{translate("Status")}</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {(bills ?? []).map((b) => (
                  <tr key={b.name} className="border-t border-zinc-100">
                    <td className="py-2 pr-3 font-medium">{b.vendor_name}</td>
                    <td className="py-2 pr-3">
                      <span className="font-mono text-xs">{b.bill_number || b.name}</span>
                      <span className="block text-xs text-zinc-400">{b.bill_date}</span>
                    </td>
                    <td className="py-2 pr-3 text-zinc-600">{translate(b.expense_category)}</td>
                    <td className={`py-2 pr-3 ${b.days_overdue ? "text-rose-700" : ""}`}>
                      {b.due_date}
                      {b.days_overdue ? <span className="ml-1 text-xs">({translate("{n}d late", { n: b.days_overdue })})</span> : null}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {fmtMoney(b.total)}
                      {b.tax_amount ? <span className="block text-xs text-zinc-400">{taxLabel()} {fmtMoney(b.tax_amount)}</span> : null}
                    </td>
                    <td className="py-2 pr-3 text-right font-medium tabular-nums">{b.outstanding ? fmtMoney(b.outstanding) : "-"}</td>
                    <td className="py-2 pr-3"><StatusBadge status={b.status} /></td>
                    <td className="py-2 text-right">
                      <div className="flex justify-end gap-1.5">
                        {canApprove && b.status === "Awaiting Approval" ? (
                          <Button variant="outline" onClick={() => void approve(b)}>{translate("Approve")}</Button>
                        ) : null}
                        {canEnter && (b.status === "Approved" || b.status === "Part Paid") ? (
                          <Button variant="outline" onClick={() => setSheet({ pay: b })}>{translate("Pay")}</Button>
                        ) : null}
                        {canEnter && b.status !== "Cancelled" && b.status !== "Paid" && !b.paid ? (
                          <Button variant="outline" onClick={() => setSheet({ cancel: b })}>{translate("Cancel")}</Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {bills && !bills.length ? (
                  <tr><td colSpan={8} className="py-8 text-center text-zinc-400">{translate("No bills here.")}</td></tr>
                ) : null}
                {!bills ? (
                  <tr><td colSpan={8} className="py-8 text-center text-zinc-400">{translate("Loading…")}</td></tr>
                ) : null}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-400">
                <tr>
                  <th className="py-2 pr-3">{translate("Vendor")}</th>
                  <th className="py-2 pr-3">{translate("Category")}</th>
                  <th className="py-2 pr-3">{translate("Contact")}</th>
                  <th className="py-2 pr-3">{translate("Terms")}</th>
                  <th className="py-2 pr-3 text-right">{translate("Overdue")}</th>
                  <th className="py-2 text-right">{translate("Owed")}</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr
                    key={v.name}
                    className={`border-t border-zinc-100 ${canEnter ? "cursor-pointer hover:bg-zinc-50" : ""} ${v.disabled ? "text-zinc-400" : ""}`}
                    onClick={() => canEnter && setSheet({ vendor: v })}
                  >
                    <td className="py-2 pr-3 font-medium">
                      {v.vendor_name}
                      {v.disabled ? <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px]">{translate("Disabled")}</span> : null}
                    </td>
                    <td className="py-2 pr-3">{translate(v.expense_category)}</td>
                    <td className="py-2 pr-3 text-zinc-600">
                      {v.contact_name || "-"}
                      {v.phone ? <span className="block text-xs text-zinc-400">{v.phone}</span> : null}
                    </td>
                    <td className="py-2 pr-3 text-xs text-zinc-500">{translate("{n} days", { n: v.payment_terms_days ?? 0 })}</td>
                    <td className={`py-2 pr-3 text-right tabular-nums ${v.overdue ? "font-medium text-rose-700" : ""}`}>{v.overdue ? fmtMoney(v.overdue) : "-"}</td>
                    <td className="py-2 text-right font-medium tabular-nums">{fmtMoney(v.balance)}</td>
                  </tr>
                ))}
                {!vendors.length ? (
                  <tr><td colSpan={6} className="py-8 text-center text-zinc-400">{translate("No vendors yet. Add the suppliers you buy from on credit.")}</td></tr>
                ) : null}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {sheet === "bill" ? (
        <NewBill vendors={vendors.filter((v) => !v.disabled)} categories={categories} onClose={() => setSheet(null)}
          onSaved={(b) => done(translate("Bill {v0} entered. It waits for approval.", { v0: b }))} />
      ) : null}
      {sheet && typeof sheet === "object" && !("pay" in sheet) && !("cancel" in sheet) ? (
        <VendorSheet vendor={sheet.vendor} categories={categories} onClose={() => setSheet(null)}
          onSaved={() => done(translate("Vendor saved."))} />
      ) : null}
      {sheet && typeof sheet === "object" && "pay" in sheet ? (
        <PayBill bill={sheet.pay} onClose={() => setSheet(null)}
          onPaid={() => done(translate("Payment recorded."))} />
      ) : null}
      {sheet && typeof sheet === "object" && "cancel" in sheet ? (
        <CancelBill bill={sheet.cancel} onClose={() => setSheet(null)}
          onDone={() => done(translate("Bill cancelled."))} />
      ) : null}
    </div>
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

function StatusBadge({ status }: { status: string }) {
  useUILanguage()
  const tone: Record<string, string> = {
    "Awaiting Approval": "bg-amber-50 text-amber-800",
    Approved: "bg-sky-50 text-sky-800",
    "Part Paid": "bg-sky-50 text-sky-800",
    Paid: "bg-emerald-50 text-emerald-800",
    Cancelled: "bg-zinc-100 text-zinc-500",
  }
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${tone[status] ?? ""}`}>{translate(status)}</span>
}

function Footer(props: { busy: boolean; disabled?: boolean; label: string; onClose: () => void; onSave: () => void }) {
  useUILanguage()
  return (
    <div className="flex justify-end gap-2">
      <Button variant="outline" onClick={props.onClose}>{translate("Close")}</Button>
      <Button disabled={props.busy || props.disabled} onClick={props.onSave}>
        {props.busy ? translate("Saving…") : translate(props.label)}
      </Button>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  useUILanguage()
  return (
    <label className="block">
      <span className="mb-1 block text-zinc-500">{translate(label)}</span>
      {children}
    </label>
  )
}

function useSave(fn: () => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const run = async () => {
    setBusy(true)
    setErr(null)
    try {
      await fn()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }
  return { busy, err, run }
}

function NewBill(props: { vendors: Vendor[]; categories: string[]; onClose: () => void; onSaved: (bill: string) => void }) {
  useUILanguage()
  const [vendor, setVendor] = useState(props.vendors[0]?.name ?? "")
  const v = props.vendors.find((x) => x.name === vendor)
  const [category, setCategory] = useState(v?.expense_category ?? "Other")
  const [number, setNumber] = useState("")
  const [billDate, setBillDate] = useState(today())
  const [due, setDue] = useState("")
  const [amount, setAmount] = useState("")
  const [rate, setRate] = useState("0")
  const [description, setDescription] = useState("")
  useEffect(() => { if (v) setCategory(v.expense_category) }, [v])
  // a preview only; the server works out the bill
  const preview = useMemo(() => {
    const a = Number(amount) || 0
    return a + Math.round(a * (Number(rate) || 0)) / 100
  }, [amount, rate])
  const { busy, err, run } = useSave(async () => {
    const out = await call<{ name: string }>("kamra.payables.create_vendor_bill", {
      property: getCurrentProperty(), vendor, bill_date: billDate, amount: Number(amount),
      tax_rate: Number(rate) || 0, expense_category: category,
      bill_number: number.trim() || undefined, due_date: due || undefined,
      description: description.trim() || undefined,
    })
    props.onSaved(out.name)
  })
  return (
    <Sheet title={translate("New bill")} description={translate("A bill from a supplier, paid later")} onClose={props.onClose}
      footer={<Footer busy={busy} disabled={!vendor || !(Number(amount) > 0)} label="Save" onClose={props.onClose} onSave={() => void run()} />}>
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        <Field label="Vendor">
          <select className={field} value={vendor} onChange={(e) => setVendor(e.target.value)}>
            {props.vendors.map((x) => <option key={x.name} value={x.name}>{x.vendor_name}</option>)}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Supplier's bill number"><input className={field} value={number} onChange={(e) => setNumber(e.target.value)} /></Field>
          <Field label="Expense category">
            <select className={field} value={category} onChange={(e) => setCategory(e.target.value)}>
              {props.categories.map((c) => <option key={c} value={c}>{translate(c)}</option>)}
            </select>
          </Field>
          <Field label="Bill date"><input type="date" className={field} value={billDate} max={today()} onChange={(e) => setBillDate(e.target.value)} /></Field>
          <Field label="Due date">
            <input type="date" className={field} value={due} min={billDate} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label="Amount before tax"><input className={field} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          <Field label={translate("{v0} rate %", { v0: taxLabel() })}>
            <select className={field} value={rate} onChange={(e) => setRate(e.target.value)}>
              {Array.from(new Set([0, ...taxRates()])).map((r) => <option key={r} value={String(r)}>{r}%</option>)}
            </select>
          </Field>
        </div>
        {!due && v ? <p className="text-xs text-zinc-500">{translate("Left empty, it is due {n} days after the bill date.", { n: v.payment_terms_days })}</p> : null}
        <Field label="Description"><textarea className={field} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
        <p className="text-right text-zinc-500">{translate("Total about {v0}", { v0: fmtMoney(preview) })}</p>
      </div>
    </Sheet>
  )
}

function VendorSheet(props: { vendor?: Vendor; categories: string[]; onClose: () => void; onSaved: () => void }) {
  useUILanguage()
  const v = props.vendor
  const [name, setName] = useState(v?.vendor_name ?? "")
  const [category, setCategory] = useState(v?.expense_category ?? "Other")
  const [terms, setTerms] = useState(String(v?.payment_terms_days ?? 30))
  const [taxId, setTaxId] = useState(v?.tax_id ?? "")
  const [contact, setContact] = useState(v?.contact_name ?? "")
  const [phone, setPhone] = useState(v?.phone ?? "")
  const [email, setEmail] = useState(v?.email ?? "")
  const [notes, setNotes] = useState(v?.notes ?? "")
  const [disabled, setDisabled] = useState(!!v?.disabled)
  const { busy, err, run } = useSave(async () => {
    await call("kamra.payables.save_vendor", {
      property: getCurrentProperty(), vendor: v?.name, vendor_name: name,
      expense_category: category, payment_terms_days: Number(terms) || 0,
      tax_id: taxId, contact_name: contact, phone, email, notes, disabled: disabled ? 1 : 0,
    })
    props.onSaved()
  })
  return (
    <Sheet title={v ? v.vendor_name : translate("New vendor")} description={translate("A supplier you buy from on credit")} onClose={props.onClose}
      footer={<Footer busy={busy} disabled={!name.trim()} label="Save" onClose={props.onClose} onSave={() => void run()} />}>
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        <Field label="Vendor name"><input className={field} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Usual expense category">
            <select className={field} value={category} onChange={(e) => setCategory(e.target.value)}>
              {props.categories.map((c) => <option key={c} value={c}>{translate(c)}</option>)}
            </select>
          </Field>
          <Field label="Pay within (days)"><input className={field} inputMode="numeric" value={terms} onChange={(e) => setTerms(e.target.value)} /></Field>
          <Field label="Tax ID"><input className={field} value={taxId} onChange={(e) => setTaxId(e.target.value)} /></Field>
          <Field label="Contact name"><input className={field} value={contact} onChange={(e) => setContact(e.target.value)} /></Field>
          <Field label="Phone"><input className={field} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <Field label="Email"><input className={field} value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        </div>
        <Field label="Notes"><textarea className={field} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {v ? (
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={disabled} onChange={(e) => setDisabled(e.target.checked)} />
            {translate("Disabled (no new bills)")}
          </label>
        ) : null}
      </div>
    </Sheet>
  )
}

function PayBill(props: { bill: Bill; onClose: () => void; onPaid: () => void }) {
  useUILanguage()
  const loc = useLocale()
  const b = props.bill
  const [amount, setAmount] = useState(String(b.outstanding))
  const [mode, setMode] = useState("Bank Transfer")
  const [reference, setReference] = useState("")
  const [date, setDate] = useState(today())
  const modes = Array.from(new Set(["Bank Transfer", "Cheque", ...loc.payment_modes]))
  const { busy, err, run } = useSave(async () => {
    await call("kamra.payables.pay_vendor_bill", {
      bill: b.name, amount: Number(amount), mode, reference: reference.trim() || undefined, payment_date: date,
    })
    props.onPaid()
  })
  return (
    <Sheet title={translate("Pay {v0}", { v0: b.vendor_name })}
      description={translate("{v0} still owed on {v1}", { v0: fmtMoney(b.outstanding), v1: b.bill_number || b.name })}
      onClose={props.onClose}
      footer={<Footer busy={busy} disabled={!(Number(amount) > 0)} label="Record payment" onClose={props.onClose} onSave={() => void run()} />}>
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount"><input className={field} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          <Field label="Date"><input type="date" className={field} value={date} min={b.bill_date} max={today()} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Paid by">
            <select className={field} value={mode} onChange={(e) => setMode(e.target.value)}>
              {modes.map((m) => <option key={m} value={m}>{translate(m)}</option>)}
            </select>
          </Field>
          <Field label="Reference"><input className={field} value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
        </div>
        <p className="text-xs text-zinc-500">{translate("This records the payment. It does not take cash from a till.")}</p>
      </div>
    </Sheet>
  )
}

function CancelBill(props: { bill: Bill; onClose: () => void; onDone: () => void }) {
  useUILanguage()
  const [reason, setReason] = useState("")
  const { busy, err, run } = useSave(async () => {
    await call("kamra.payables.cancel_vendor_bill", { bill: props.bill.name, reason })
    props.onDone()
  })
  return (
    <Sheet title={translate("Cancel bill")} description={`${props.bill.vendor_name} · ${props.bill.bill_number || props.bill.name}`} onClose={props.onClose}
      footer={<Footer busy={busy} disabled={!reason.trim()} label="Cancel bill" onClose={props.onClose} onSave={() => void run()} />}>
      <div className="space-y-4 text-sm">
        {err ? <p className="text-rose-600">{translate(err)}</p> : null}
        <Field label="Why"><textarea className={field} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      </div>
    </Sheet>
  )
}
