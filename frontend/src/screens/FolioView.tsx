import { useCallback, useEffect, useState } from "react"
import { ArrowLeft, Printer } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"

const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })

interface InvoiceData {
  folio: {
    name: string
    status: "Open" | "Closed"
    invoice_number: string | null
    guest_name: string
    charges: {
      name: string
      posting_date: string
      charge_type: string
      description: string
      amount: number
      gst_rate: number
      gst_amount: number
      total: number
    }[]
    payments: {
      posting_date: string
      mode: string
      amount: number
      reference: string | null
    }[]
    charges_total: number
    tax_total: number
    grand_total: number
    payments_total: number
    balance: number
  }
  property: {
    name: string
    address: string
    gstin: string | null
    phone: string | null
    email: string | null
  }
  stay: {
    reservation: string
    check_in: string
    check_out: string
    nights: number
    room: string | null
    company: string | null
  }
  gst_summary: {
    rate: number
    taxable: number
    cgst: number
    sgst: number
    total_tax: number
  }[]
  bill_to: { name: string; gstin: string | null } | null
}

const CHARGE_TYPES = [
  "Food & Beverage", "Minibar", "Laundry", "Spa",
  "Early Check-in", "Late Checkout", "Discount", "Misc",
]
const PAY_MODES = ["Cash", "Card", "UPI", "Bank Transfer", "Payment Link"]

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface SiblingFolio {
  name: string
  folio_type: string
  status: string
  balance: number
}

export default function FolioView() {
  const { name } = useParams()
  const [data, setData] = useState<InvoiceData | null>(null)
  const [siblings, setSiblings] = useState<SiblingFolio[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [charge, setCharge] = useState({
    charge_type: "Food & Beverage", description: "", amount: "", gst_rate: "5",
  })
  const [payment, setPayment] = useState({ mode: "UPI", amount: "", reference: "" })

  const load = useCallback(() => {
    if (name)
      call<InvoiceData>("kamra.api.folio_invoice", { folio: name })
        .then((d) => {
          setData(d)
          setPayment((p) => ({ ...p, amount: String(d.folio.balance || "") }))
          return call<SiblingFolio[]>("kamra.api.reservation_folios", {
            reservation: d.stay.reservation,
          })
        })
        .then((s) => s && setSiblings(s))
        .catch((e) => setError(serverError(e)))
  }, [name])

  useEffect(load, [load])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data)
    return <p className="py-10 text-center text-sm text-zinc-400">Loading…</p>

  const { folio, property, stay, gst_summary } = data
  const open = folio.status === "Open"

  return (
    <div>
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link
          to="/billing"
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Billing
        </Link>
        <div className="flex gap-2">
          {siblings.length > 1 && (
            <div className="flex items-center gap-1 rounded-lg bg-zinc-100 p-1 text-xs">
              {siblings.map((s) => (
                <Link
                  key={s.name}
                  to={`/billing/${encodeURIComponent(s.name)}`}
                  className={
                    s.name === folio.name
                      ? "rounded-md bg-white px-2 py-1 font-medium shadow-sm"
                      : "px-2 py-1 text-zinc-500 hover:text-zinc-800"
                  }
                >
                  {s.folio_type}
                </Link>
              ))}
            </div>
          )}
          {open && folio.balance > 0 && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await call<{ url: string }>(
                    "kamra.api.folio_payment_link",
                    { folio: folio.name },
                  )
                  navigator.clipboard.writeText(r.url)
                })
              }
              title="Creates a Razorpay link for the balance and copies it"
            >
              Payment link
            </Button>
          )}
          {open && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                act(() =>
                  call("kamra.api.split_folio", {
                    reservation: data.stay.reservation,
                    folio_type: siblings.some((s) => s.folio_type === "Company")
                      ? "Extra"
                      : "Company",
                  }),
                )
              }
            >
              Split folio
            </Button>
          )}
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden />
            Print {folio.invoice_number ? "invoice" : "folio"}
          </Button>
          {open && (
            <Button
              disabled={busy}
              onClick={() =>
                act(() => call("kamra.api.close_folio", { folio: folio.name }))
              }
            >
              Close & generate invoice
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 print:hidden">
          {error}
        </div>
      )}

      {/* printable document */}
      <Card className="print:border-0 print:shadow-none">
        <CardContent className="py-6">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 pb-5">
            <div>
              <h1 className="text-xl font-semibold">{property.name}</h1>
              <p className="text-sm text-zinc-500">{property.address}</p>
              <p className="text-sm text-zinc-500">
                {property.gstin && <>GSTIN: {property.gstin} · </>}
                {property.phone}
              </p>
            </div>
            <div className="text-right">
              <p className="text-lg font-semibold">
                {folio.invoice_number ?? folio.name}
              </p>
              <p className="text-sm text-zinc-500">
                {folio.invoice_number ? "Tax Invoice" : "Folio (unsettled)"}
              </p>
              <Badge tone={open ? "amber" : "green"}>{folio.status}</Badge>
            </div>
          </div>

          {data.bill_to && (
            <div className="mb-4 rounded-lg bg-zinc-50 px-4 py-2.5 text-sm">
              <span className="text-zinc-500">Bill to: </span>
              <span className="font-medium">{data.bill_to.name}</span>
              {data.bill_to.gstin && (
                <span className="text-zinc-500"> · GSTIN {data.bill_to.gstin}</span>
              )}
            </div>
          )}
          <div className="mb-6 grid gap-1 text-sm sm:grid-cols-2">
            <p>
              <span className="text-zinc-500">Guest: </span>
              <span className="font-medium">{folio.guest_name}</span>
              {stay.company && (
                <span className="text-zinc-500"> · {stay.company}</span>
              )}
            </p>
            <p>
              <span className="text-zinc-500">Stay: </span>
              {stay.check_in} → {stay.check_out} · {stay.nights} night
              {stay.nights === 1 ? "" : "s"}
              {stay.room && ` · Room ${stay.room.split("-").pop()}`}
            </p>
          </div>

          <table className="mb-5 w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                <th className="py-2 pr-3">Date</th>
                <th className="py-2 pr-3">Item</th>
                <th className="py-2 pr-3 text-right">Amount ₹</th>
                <th className="py-2 pr-3 text-right">GST %</th>
                <th className="py-2 pr-3 text-right">GST ₹</th>
                <th className="py-2 text-right">Total ₹</th>
                {open && siblings.filter((s) => s.status === "Open").length > 1 && (
                  <th className="py-2 pl-3 print:hidden" aria-label="Move" />
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {folio.charges.map((c, i) => (
                <tr key={i}>
                  <td className="py-2 pr-3 text-zinc-500">{c.posting_date}</td>
                  <td className="py-2 pr-3">
                    <span className="font-medium">{c.charge_type}</span>
                    {c.description && (
                      <span className="text-zinc-500"> — {c.description}</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-right">{inr(c.amount)}</td>
                  <td className="py-2 pr-3 text-right">{c.gst_rate}%</td>
                  <td className="py-2 pr-3 text-right">{inr(c.gst_amount)}</td>
                  <td className="py-2 text-right font-medium">{inr(c.total)}</td>
                  {open && siblings.filter((s) => s.status === "Open").length > 1 && (
                    <td className="py-2 pl-3 text-right print:hidden">
                      <select
                        className="rounded-md border border-zinc-200 px-1.5 py-1 text-xs text-zinc-500"
                        value=""
                        aria-label="Move charge to another folio"
                        onChange={(e) =>
                          e.target.value &&
                          act(() =>
                            call("kamra.api.transfer_folio_charge", {
                              from_folio: folio.name,
                              charge_row: c.name,
                              to_folio: e.target.value,
                            }),
                          )
                        }
                      >
                        <option value="">Move…</option>
                        {siblings
                          .filter(
                            (s) => s.status === "Open" && s.name !== folio.name,
                          )
                          .map((s) => (
                            <option key={s.name} value={s.name}>
                              → {s.folio_type}
                            </option>
                          ))}
                      </select>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mb-6 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                GST summary
              </h3>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-zinc-100">
                  {gst_summary.map((r) => (
                    <tr key={r.rate}>
                      <td className="py-1.5 pr-3">{r.rate}% slab</td>
                      <td className="py-1.5 pr-3 text-right text-zinc-500">
                        taxable ₹{inr(r.taxable)}
                      </td>
                      <td className="py-1.5 text-right">
                        CGST ₹{inr(r.cgst)} · SGST ₹{inr(r.sgst)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="space-y-1.5 text-sm sm:text-right">
              <p className="text-zinc-500">
                Charges: <span className="text-zinc-900">₹{inr(folio.charges_total)}</span>
              </p>
              <p className="text-zinc-500">
                GST: <span className="text-zinc-900">₹{inr(folio.tax_total)}</span>
              </p>
              <p className="text-lg font-semibold">
                Grand total: ₹{inr(folio.grand_total)}
              </p>
              <p className="text-zinc-500">
                Paid: ₹{inr(folio.payments_total)} · Balance:{" "}
                <span
                  className={
                    folio.balance > 0
                      ? "font-medium text-amber-600"
                      : "font-medium text-emerald-600"
                  }
                >
                  ₹{inr(folio.balance)}
                </span>
              </p>
            </div>
          </div>

          {folio.payments.length > 0 && (
            <div className="text-sm">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Payments
              </h3>
              <ul className="divide-y divide-zinc-100">
                {folio.payments.map((p, i) => (
                  <li key={i} className="flex justify-between py-1.5">
                    <span>
                      {p.posting_date} · {p.mode}
                      {p.reference && (
                        <span className="text-zinc-400"> · {p.reference}</span>
                      )}
                    </span>
                    <span>₹{inr(p.amount)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {open && (
        <div className="mt-4 grid gap-4 md:grid-cols-2 print:hidden">
          <Card>
            <CardHeader>
              <CardTitle>Post a charge</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-2">
              <select
                className={inputCls}
                value={charge.charge_type}
                onChange={(e) =>
                  setCharge({ ...charge, charge_type: e.target.value })
                }
              >
                {CHARGE_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <input
                className={`${inputCls} flex-1`}
                placeholder="Description"
                value={charge.description}
                onChange={(e) =>
                  setCharge({ ...charge, description: e.target.value })
                }
              />
              <input
                className={`${inputCls} w-24`}
                type="number"
                placeholder="₹"
                value={charge.amount}
                onChange={(e) => setCharge({ ...charge, amount: e.target.value })}
              />
              <select
                className={inputCls}
                value={charge.gst_rate}
                onChange={(e) =>
                  setCharge({ ...charge, gst_rate: e.target.value })
                }
              >
                {["0", "5", "12", "18", "28"].map((r) => (
                  <option key={r} value={r}>
                    GST {r}%
                  </option>
                ))}
              </select>
              <Button
                disabled={busy || !charge.amount}
                onClick={() =>
                  act(() =>
                    call("kamra.api.add_folio_charge", {
                      folio: folio.name,
                      ...charge,
                      amount: Number(charge.amount),
                      gst_rate: Number(charge.gst_rate),
                    }),
                  )
                }
              >
                Post
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Record a payment</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-2">
              <select
                className={inputCls}
                value={payment.mode}
                onChange={(e) => setPayment({ ...payment, mode: e.target.value })}
              >
                {PAY_MODES.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
              <input
                className={`${inputCls} w-28`}
                type="number"
                placeholder="₹"
                value={payment.amount}
                onChange={(e) =>
                  setPayment({ ...payment, amount: e.target.value })
                }
              />
              <input
                className={`${inputCls} flex-1`}
                placeholder="Reference (optional)"
                value={payment.reference}
                onChange={(e) =>
                  setPayment({ ...payment, reference: e.target.value })
                }
              />
              <Button
                disabled={busy || !payment.amount}
                onClick={() =>
                  act(() =>
                    call("kamra.api.add_folio_payment", {
                      folio: folio.name,
                      mode: payment.mode,
                      amount: Number(payment.amount),
                      reference: payment.reference || undefined,
                    }),
                  )
                }
              >
                Record
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
