import { Fragment, useCallback, useEffect, useState } from "react"
import { ArrowLeft, ArrowRightLeft, Printer, Trash2, X } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import LinkedRecords from "../components/LinkedRecords"
import { loadLocale, taxRates } from "../lib/money"
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
      payment_kind?: string | null
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
    legal_name: string | null
    logo_url: string | null
    address: string
    state: string | null
    gstin: string | null
    phone: string | null
    email: string | null
    sac: string | null
    place_of_supply: string | null
  }
  stay: {
    reservation: string
    check_in: string
    check_out: string
    nights: number
    room: string | null
    company: string | null
    group_booking: string | null
    booked_by_name: string | null
    booked_by_phone: string | null
    contact_preference: string | null
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
  grand_total: number
  payments_total: number
}

/** A distinct label per folio - Extras get numbered when there's more than one. */
function folioLabel(siblings: SiblingFolio[], s: SiblingFolio) {
  if (s.folio_type !== "Extra") return s.folio_type
  const extras = siblings.filter((x) => x.folio_type === "Extra")
  if (extras.length <= 1) return "Extra"
  return `Extra ${extras.findIndex((x) => x.name === s.name) + 1}`
}
const isEmptyFolio = (s: SiblingFolio) =>
  !s.grand_total && !s.payments_total

export default function FolioView() {
  const { name } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<InvoiceData | null>(null)
  const [siblings, setSiblings] = useState<SiblingFolio[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [charge, setCharge] = useState({
    charge_type: "Food & Beverage", description: "", amount: "", gst_rate: "5",
    is_alcohol: false,
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [voidFor, setVoidFor] = useState<string | null>(null)
  const [partVal, setPartVal] = useState("")
  const [payment, setPayment] = useState({ mode: "UPI", amount: "", reference: "", kind: "Payment" })
  const [refund, setRefund] = useState<{ amount: string; mode: string; reason: string } | null>(null)
  const [showCancel, setShowCancel] = useState(false)
  const [cancelReason, setCancelReason] = useState("")
  const [allowance, setAllowance] = useState({ amount: "", reason: "", gst_rate: "0" })
  // cashier PIN: when the property demands it, every money action carries it
  const [pinStatus, setPinStatus] = useState<{ required: boolean; has_pin: boolean } | null>(null)
  const [pin, setPin] = useState("")
  const [newPin, setNewPin] = useState("")

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

  const [rates, setRates] = useState<number[]>(taxRates())
  useEffect(() => {
    loadLocale().then((l) => setRates(l.tax_rates))
  }, [])
  useEffect(() => {
    call<{ required: boolean; has_pin: boolean }>(
      "kamra.api.cashier_pin_status",
      { property: getCurrentProperty() },
    )
      .then(setPinStatus)
      .catch(() => setPinStatus(null))
  }, [])

  /** PIN travels with every money call when the property demands it. */
  const withPin = (params: Record<string, unknown>) =>
    pinStatus?.required ? { ...params, pin } : params

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

  function removeFolio(target: SiblingFolio) {
    act(async () => {
      await call("kamra.api.delete_folio", { folio: target.name })
      if (target.name === name) {
        const guest = siblings.find((s) => s.folio_type === "Guest")
        navigate(
          guest ? `/billing/${encodeURIComponent(guest.name)}` : "/billing",
        )
      }
    })
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
            <div className="flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100 p-1">
              {siblings.map((s) => {
                const active = s.name === folio.name
                const empty = isEmptyFolio(s)
                const canDelete =
                  empty && s.folio_type !== "Guest" && s.folio_type !== "Group"
                return (
                  <div
                    key={s.name}
                    className={
                      "group flex items-center rounded-md " +
                      (active ? "bg-white shadow-sm" : "")
                    }
                  >
                    <Link
                      to={`/billing/${encodeURIComponent(s.name)}`}
                      className={
                        "flex items-center gap-1.5 px-2.5 py-1 text-xs " +
                        (active
                          ? "font-medium text-zinc-800"
                          : "text-zinc-500 hover:text-zinc-800")
                      }
                    >
                      {folioLabel(siblings, s)}
                      <span
                        className={
                          "tabular-nums " +
                          (s.balance > 0 ? "text-amber-600" : "text-zinc-400")
                        }
                      >
                        ₹{inr(s.balance)}
                      </span>
                    </Link>
                    {canDelete && (
                      <button
                        aria-label={`Delete empty ${folioLabel(siblings, s)} folio`}
                        title="Delete this empty folio"
                        disabled={busy}
                        onClick={() => removeFolio(s)}
                        className="pr-1.5 text-zinc-300 hover:text-rose-500"
                      >
                        <X className="size-3.5" />
                      </button>
                    )}
                  </div>
                )
              })}
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
              title={`Creates a payment link for the balance and copies it - send to the ${
                data.stay.contact_preference === "Booker" &&
                data.stay.booked_by_name
                  ? `booker, ${data.stay.booked_by_name}${data.stay.booked_by_phone ? ` (${data.stay.booked_by_phone})` : ""}`
                  : data.stay.contact_preference === "Both" &&
                      data.stay.booked_by_name
                    ? `guest and the booker (${data.stay.booked_by_name})`
                    : "guest"
              }`}
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
          {open &&
            data.stay.group_booking &&
            !siblings.some((s) => s.folio_type === "Group") && (
              <Button
                variant="outline"
                disabled={busy}
                title="One consolidated company bill across every room of the group"
                onClick={() =>
                  act(() =>
                    call("kamra.api.group_master_folio", {
                      group_booking: data.stay.group_booking,
                    }),
                  )
                }
              >
                Group folio
              </Button>
            )}
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden />
            Print {folio.invoice_number ? "invoice" : "folio"}
          </Button>
          {open &&
            folio.balance === 0 &&
            folio.charges.length > 0 && (
              <Button
                variant="outline"
                disabled={busy}
                title="Interim invoice: freeze this paid folio and keep the stay running on a fresh one - for long stays settled every few days"
                onClick={() =>
                  act(async () => {
                    const r = await call<{ new_folio: string }>(
                      "kamra.api.part_settle_folio",
                      withPin({ folio: folio.name }),
                    )
                    navigate(`/billing/${encodeURIComponent(r.new_folio)}`)
                  })
                }
              >
                Settle &amp; continue stay
              </Button>
            )}
          {!open && folio.invoice_number && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setShowCancel((s) => !s)}
            >
              Cancel invoice
            </Button>
          )}
          {open && (
            <Button
              disabled={busy}
              onClick={() =>
                act(() => call("kamra.api.close_folio", withPin({ folio: folio.name })))
              }
            >
              Close & generate invoice
            </Button>
          )}
        </div>
      </div>

      {showCancel && !open && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm print:hidden">
          <span className="text-amber-800">
            Cancel {folio.invoice_number}? The number goes on the cancelled
            register and the folio reopens for correction.
          </span>
          <input
            className="min-w-56 flex-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm"
            placeholder="Reason (required - goes on the record)"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
          <Button
            variant="outline"
            disabled={busy || !cancelReason.trim()}
            onClick={() =>
              act(async () => {
                await call("kamra.api.cancel_invoice", withPin({
                  folio: folio.name,
                  reason: cancelReason.trim(),
                }))
                setShowCancel(false)
                setCancelReason("")
              })
            }
          >
            Confirm cancel
          </Button>
        </div>
      )}

      <div className="mb-4 print:hidden">
        <LinkedRecords doctype="Reservation" name={stay.reservation} />
      </div>

      {pinStatus?.required && !pinStatus.has_pin && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm print:hidden">
          <span className="text-sky-800">
            This property requires a cashier PIN on money actions - set yours
            (4–8 digits):
          </span>
          <input
            className="w-28 rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-sm"
            type="password"
            inputMode="numeric"
            placeholder="New PIN"
            value={newPin}
            onChange={(e) => setNewPin(e.target.value)}
          />
          <Button
            variant="outline"
            disabled={busy || newPin.trim().length < 4}
            onClick={() =>
              act(async () => {
                await call("kamra.api.set_cashier_pin", { pin: newPin.trim() })
                setNewPin("")
                setPinStatus((s) => (s ? { ...s, has_pin: true } : s))
              })
            }
          >
            Set PIN
          </Button>
        </div>
      )}
      {pinStatus?.required && pinStatus.has_pin && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg bg-zinc-50 px-4 py-2 text-sm text-zinc-600 print:hidden">
          <span>Cashier PIN (needed for payments, settling and invoices):</span>
          <input
            className="w-24 rounded-lg border border-zinc-300 bg-white px-3 py-1 text-sm"
            type="password"
            inputMode="numeric"
            aria-label="Cashier PIN"
            placeholder="••••"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
          />
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 print:hidden">
          {error}
        </div>
      )}

      {/* printable document */}
      <Card className="print:border-0 print:shadow-none">
        <CardContent className="py-6">
          {folio.invoice_number && (
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Tax Invoice
            </p>
          )}
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 pb-5">
            <div className="flex items-start gap-3">
              {property.logo_url && (
                <img
                  src={property.logo_url}
                  alt=""
                  className="h-12 w-12 shrink-0 rounded object-contain"
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).style.display = "none"
                  }}
                />
              )}
              <div>
                <h1 className="text-xl font-semibold">
                  {property.legal_name || property.name}
                </h1>
                {property.legal_name &&
                  property.legal_name !== property.name && (
                    <p className="text-sm text-zinc-500">{property.name}</p>
                  )}
                <p className="text-sm text-zinc-500">{property.address}</p>
                <p className="text-sm text-zinc-500">
                  {property.gstin && (
                    <>
                      GSTIN: <span className="font-medium">{property.gstin}</span>{" "}
                      ·{" "}
                    </>
                  )}
                  {property.phone}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-lg font-semibold">
                {folio.invoice_number ?? folio.name}
              </p>
              <p className="text-sm text-zinc-500">
                {folio.invoice_number ? "Tax Invoice" : "Folio (unsettled)"}
              </p>
              {folio.invoice_number && property.place_of_supply && (
                <p className="mt-1 text-xs text-zinc-500">
                  Place of supply: {property.place_of_supply}
                  <br />
                  SAC: {property.sac}
                </p>
              )}
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

          {(() => {
            const targets = siblings.filter(
              (s) => s.status === "Open" && s.name !== folio.name,
            )
            // moving is always possible on an open folio - the Move panel
            // can mint a fresh Extra/Company folio as the destination
            const editable = open // charges can be voided on any open folio
            return (
              <>
                {open && selected.size > 0 && (() => {
                  const sel = folio.charges.filter((c) => selected.has(c.name))
                  const selTotal = sel.reduce((s, c) => s + (c.total || 0), 0)
                  const one = sel.length === 1 ? sel[0] : null
                  const v = partVal.trim()
                  const isPct = v.endsWith("%")
                  const num = Number(v.replace("%", ""))
                  const partOk =
                    !!one && !!v && num > 0 &&
                    (isPct ? num < 100 : num < (one.amount || 0))
                  const partBad = !!one && !!v && !partOk
                  const movedTotal = !one || !partOk
                    ? selTotal
                    : isPct
                      ? ((one.total || 0) * num) / 100
                      : num * (1 + (one.gst_rate || 0) / 100)
                  const moveTo = (to: string) =>
                    act(async () => {
                      if (one && partOk) {
                        await call("kamra.api.split_folio_charge", {
                          from_folio: folio.name,
                          charge_row: one.name,
                          to_folio: to,
                          percent: isPct ? num : null,
                          amount: isPct ? null : num,
                        })
                      } else {
                        await call("kamra.api.transfer_folio_charges", {
                          from_folio: folio.name,
                          charge_rows: [...selected],
                          to_folio: to,
                        })
                      }
                      setSelected(new Set())
                      setPartVal("")
                    })
                  const moveToNew = (type: "Extra" | "Company") =>
                    act(async () => {
                      const r = await call<{ folio: string }>(
                        "kamra.api.split_folio",
                        { reservation: data.stay.reservation, folio_type: type },
                      )
                      if (one && partOk) {
                        await call("kamra.api.split_folio_charge", {
                          from_folio: folio.name,
                          charge_row: one.name,
                          to_folio: r.folio,
                          percent: isPct ? num : null,
                          amount: isPct ? null : num,
                        })
                      } else {
                        await call("kamra.api.transfer_folio_charges", {
                          from_folio: folio.name,
                          charge_rows: [...selected],
                          to_folio: r.folio,
                        })
                      }
                      setSelected(new Set())
                      setPartVal("")
                    })
                  return (
                    <div className="mb-3 rounded-xl border border-brand-200 bg-brand-50/40 p-3 text-sm print:hidden">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">
                          {sel.length} line{sel.length > 1 ? "s" : ""} · ₹
                          {inr(selTotal)} selected
                        </span>
                        {one && (
                          <span className="inline-flex items-center gap-1.5 text-xs text-zinc-600">
                            <span>· move only</span>
                            <input
                              className="w-24 rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs"
                              aria-label="Part to move (percent, or ₹ before GST)"
                              placeholder="30% or 1500"
                              value={partVal}
                              onChange={(e) => setPartVal(e.target.value)}
                            />
                            <span className="text-zinc-400">
                              (₹ = before GST)
                            </span>
                          </span>
                        )}
                        <button
                          className="ml-auto text-xs text-zinc-400 hover:text-zinc-700"
                          onClick={() => {
                            setSelected(new Set())
                            setPartVal("")
                          }}
                        >
                          Clear
                        </button>
                      </div>
                      {partBad && (
                        <p className="mt-1.5 text-xs text-rose-600">
                          Enter 1–99%, or a ₹ amount under the line's ₹
                          {inr(one!.amount)} (before GST).
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <span className="text-xs text-zinc-500">
                          Send ₹{inr(movedTotal)} to
                        </span>
                        {targets.map((s) => (
                          <button
                            key={s.name}
                            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs hover:border-brand-400 disabled:opacity-50"
                            disabled={busy || partBad}
                            onClick={() => moveTo(s.name)}
                          >
                            <span className="font-medium">
                              {folioLabel(siblings, s)}
                            </span>
                            <span
                              className={
                                s.balance > 0
                                  ? "ml-1.5 text-amber-600"
                                  : "ml-1.5 text-zinc-400"
                              }
                            >
                              owes ₹{inr(s.balance)}
                            </span>
                          </button>
                        ))}
                        <button
                          className="rounded-lg border border-dashed border-zinc-300 bg-white px-2.5 py-1.5 text-xs text-zinc-600 hover:border-brand-400 disabled:opacity-50"
                          disabled={busy || partBad}
                          onClick={() => moveToNew("Company")}
                        >
                          + New Company folio
                        </button>
                        <button
                          className="rounded-lg border border-dashed border-zinc-300 bg-white px-2.5 py-1.5 text-xs text-zinc-600 hover:border-brand-400 disabled:opacity-50"
                          disabled={busy || partBad}
                          onClick={() => moveToNew("Extra")}
                        >
                          + New Extra folio
                        </button>
                      </div>
                    </div>
                  )
                })()}
                <table className="mb-5 w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                      {open && (
                        <th className="w-6 py-2 pr-2 print:hidden" aria-label="Select" />
                      )}
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3">Item</th>
                      <th className="py-2 pr-3 text-right">Amount ₹</th>
                      <th className="py-2 pr-3 text-right">GST %</th>
                      <th className="py-2 pr-3 text-right">GST ₹</th>
                      <th className="py-2 text-right">Total ₹</th>
                      {editable && (
                        <th className="py-2 pl-3 print:hidden" aria-label="Actions" />
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {folio.charges.map((c, i) => (
                      <Fragment key={c.name ?? i}>
                        <tr>
                          {open && (
                            <td className="py-2 pr-2 print:hidden">
                              <input
                                type="checkbox"
                                className="size-3.5 accent-brand-600"
                                aria-label="Select charge"
                                checked={selected.has(c.name)}
                                onChange={(e) =>
                                  setSelected((prev) => {
                                    const next = new Set(prev)
                                    if (e.target.checked) next.add(c.name)
                                    else next.delete(c.name)
                                    return next
                                  })
                                }
                              />
                            </td>
                          )}
                          <td className="py-2 pr-3 text-zinc-500">{c.posting_date}</td>
                          <td className="py-2 pr-3">
                            <span className="font-medium">{c.charge_type}</span>
                            {c.description && (
                              <span className="text-zinc-500"> - {c.description}</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-right">{inr(c.amount)}</td>
                          <td className="py-2 pr-3 text-right">{c.gst_rate}%</td>
                          <td className="py-2 pr-3 text-right">{inr(c.gst_amount)}</td>
                          <td className="py-2 text-right font-medium">{inr(c.total)}</td>
                          {editable && (
                            <td className="relative whitespace-nowrap py-2 pl-3 text-right print:hidden">
                              {c.charge_type !== "Allowance" &&
                                (voidFor === c.name ? (
                                  <span className="mr-1.5 inline-flex items-center gap-1">
                                    <button
                                      className="rounded-md border border-rose-300 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
                                      disabled={busy}
                                      onClick={() =>
                                        act(async () => {
                                          await call("kamra.api.void_folio_charge",
                                            withPin({ folio: folio.name, charge_row: c.name }))
                                          setVoidFor(null)
                                        })
                                      }
                                    >
                                      Confirm void
                                    </button>
                                    <button
                                      className="text-xs text-zinc-400 hover:text-zinc-700"
                                      onClick={() => setVoidFor(null)}
                                    >
                                      Cancel
                                    </button>
                                  </span>
                                ) : (
                                  <button
                                    aria-label="Void this charge"
                                    className="mr-1.5 inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:border-rose-400 hover:text-rose-700"
                                    onClick={() => setVoidFor(c.name)}
                                  >
                                    <Trash2 className="size-3" aria-hidden />
                                    Void
                                  </button>
                                ))}
                              {open && !selected.has(c.name) && (
                                <button
                                  aria-label="Move or split this charge"
                                  className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:border-brand-400 hover:text-zinc-800"
                                  onClick={() =>
                                    setSelected((prev) => new Set(prev).add(c.name))
                                  }
                                >
                                  <ArrowRightLeft className="size-3" aria-hidden />
                                  Move
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </>
            )
          })()}

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
                      {p.payment_kind && p.payment_kind !== "Payment" && (
                        <span className={"ml-1.5 rounded px-1.5 py-0.5 text-[10px] font-semibold " +
                          (p.payment_kind === "Refund" ? "bg-rose-50 text-rose-600"
                            : p.payment_kind === "Security Deposit" ? "bg-violet-50 text-violet-700"
                              : "bg-sky-50 text-sky-700")}>
                          {p.payment_kind}
                        </span>
                      )}
                      {p.reference && (
                        <span className="text-zinc-400"> · {p.reference}</span>
                      )}
                    </span>
                    <span className={Number(p.amount) < 0 ? "font-medium text-rose-600" : ""}>₹{inr(p.amount)}</span>
                  </li>
                ))}
              </ul>
              {refund ? (
                <div className="mt-2 flex flex-wrap items-end gap-2 rounded-lg border border-rose-200 bg-rose-50 p-2">
                  <input className={`${inputCls} w-24`} type="number" placeholder="₹"
                    value={refund.amount} onChange={(e) => setRefund({ ...refund, amount: e.target.value })} />
                  <select className={inputCls} value={refund.mode}
                    onChange={(e) => setRefund({ ...refund, mode: e.target.value })}>
                    {PAY_MODES.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <input className={`${inputCls} flex-1`} placeholder="Reason (required — e.g. deposit returned)"
                    value={refund.reason} onChange={(e) => setRefund({ ...refund, reason: e.target.value })} />
                  <Button variant="outline" className="text-rose-600" disabled={busy || !refund.amount || !refund.reason.trim()}
                    onClick={() => act(async () => {
                      await call("kamra.api.refund_folio_payment", withPin({
                        folio: folio.name, amount: Number(refund.amount),
                        mode: refund.mode, reason: refund.reason,
                      }))
                      setRefund(null)
                    })}>
                    Refund
                  </Button>
                  <Button variant="ghost" onClick={() => setRefund(null)}>✕</Button>
                </div>
              ) : (
                <button className="mt-1 text-xs font-medium text-rose-600 hover:underline"
                  onClick={() => setRefund({ amount: "", mode: "Cash", reason: "" })}>
                  Refund money (deposit return / over-collection)
                </button>
              )}
            </div>
          )}

          {folio.invoice_number && (
            <div className="mt-8 flex items-end justify-between border-t border-zinc-200 pt-4 text-xs text-zinc-500">
              <p className="max-w-md">
                This is a computer-generated tax invoice under the GST Act.
                {property.gstin
                  ? " Amounts are inclusive of GST at the rates shown."
                  : ""}
              </p>
              <div className="text-center">
                <div className="mb-1 h-8 w-40 border-b border-zinc-300" />
                For {property.legal_name || property.name}
                <br />
                Authorised signatory
              </div>
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
                {rates.map((n) => String(n)).map((r) => (
                  <option key={r} value={r}>
                    GST {r}%
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-sm text-zinc-600">
                <input
                  type="checkbox"
                  className="size-4 accent-brand-600"
                  checked={charge.is_alcohol}
                  onChange={(e) =>
                    setCharge({ ...charge, is_alcohol: e.target.checked })
                  }
                />
                Alcohol
              </label>
              <Button
                disabled={busy || !charge.amount}
                onClick={() =>
                  act(() =>
                    call("kamra.api.add_folio_charge", {
                      folio: folio.name,
                      ...charge,
                      amount: Number(charge.amount),
                      gst_rate: Number(charge.gst_rate),
                      is_alcohol: charge.is_alcohol ? 1 : 0,
                    }),
                  )
                }
              >
                Post
              </Button>
              <div className="mt-1 w-full border-t border-zinc-100 pt-3">
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Pass an allowance
                  <span className="ml-1.5 normal-case tracking-normal">
                    - write off part of the bill, with a reason
                  </span>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <input
                    className={`${inputCls} w-24`}
                    type="number"
                    placeholder="₹"
                    value={allowance.amount}
                    onChange={(e) =>
                      setAllowance({ ...allowance, amount: e.target.value })
                    }
                  />
                  <select
                    className={inputCls}
                    value={allowance.gst_rate}
                    onChange={(e) =>
                      setAllowance({ ...allowance, gst_rate: e.target.value })
                    }
                  >
                    {rates.map((n) => String(n)).map((r) => (
                      <option key={r} value={r}>
                        GST {r}%
                      </option>
                    ))}
                  </select>
                  <input
                    className={`${inputCls} min-w-40 flex-1`}
                    placeholder="Reason (required)"
                    value={allowance.reason}
                    onChange={(e) =>
                      setAllowance({ ...allowance, reason: e.target.value })
                    }
                  />
                  <Button
                    variant="outline"
                    disabled={busy || !allowance.amount || !allowance.reason.trim()}
                    onClick={() =>
                      act(async () => {
                        await call("kamra.api.post_allowance", withPin({
                          folio: folio.name,
                          amount: Number(allowance.amount),
                          reason: allowance.reason.trim(),
                          gst_rate: Number(allowance.gst_rate),
                        }))
                        setAllowance({ amount: "", reason: "", gst_rate: "0" })
                      })
                    }
                  >
                    Allow
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Record a payment</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-2">
              <select
                className={inputCls}
                value={payment.kind}
                title="What this money is: against the bill, an advance, or a refundable deposit"
                onChange={(e) => setPayment({ ...payment, kind: e.target.value })}
              >
                {["Payment", "Advance", "Security Deposit"].map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
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
                    call("kamra.api.add_folio_payment", withPin({
                      folio: folio.name,
                      mode: payment.mode,
                      kind: payment.kind,
                      amount: Number(payment.amount),
                      reference: payment.reference || undefined,
                    })),
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
