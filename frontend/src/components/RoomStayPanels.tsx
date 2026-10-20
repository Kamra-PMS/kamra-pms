/*  The front office's work for the guest in a room, inside the room panel:
    guest requests (service tickets) and the stay's bill. Everything goes
    through the existing endpoints and their role gates: create_ticket /
    advance_ticket, post_stay_charge (billing rules pick the folio) and
    add_folio_payment (cashier PIN and open till rules). */

import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { fmtMoney, loadLocale, locale, useLocale } from "../lib/money"
import { useCashierAuth } from "../lib/cashierAuth"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import type { RoomDetail } from "../lib/rooms"

const inputCls =
  "block min-h-11 w-full min-w-0 rounded-lg border border-zinc-300 bg-white px-3 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const CATEGORIES = [
  "Housekeeping", "Room Service", "Maintenance", "Front Desk", "Concierge", "Complaint", "Other",
]
const PRIORITIES = ["Low", "Medium", "High", "Urgent"]
const CHARGE_TYPES = [
  "Food & Beverage", "Minibar", "Laundry", "Spa",
  "Early Check-in", "Late Checkout", "Pet Charge", "Misc",
]

function Note({ tone, children }: { tone: "error" | "ok"; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "mb-3 rounded-lg border px-3 py-2 text-sm",
        tone === "error"
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-800",
      )}
    >
      {children}
    </div>
  )
}

// --- Guest requests -----------------------------------------------------------

interface Ticket {
  name: string
  subject: string
  category: string
  priority: string
  status: string
  room: string | null
  due_by: string | null
  overdue: boolean
  creation: string
}

export function GuestRequests({ d, onChanged }: { d: RoomDetail; onChanged: () => void }) {
  const { t } = useT()
  const [rows, setRows] = useState<Ticket[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ subject: "", category: "Housekeeping", priority: "Medium" })

  const load = useCallback(() => {
    call<Ticket[]>("kamra.api.tickets_list", { property: d.room.property })
      .then((all) => setRows(all.filter((x) => x.room === d.room.name)))
      .catch((e) => setError(serverError(e)))
  }, [d.room.property, d.room.name])
  useEffect(load, [load])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
      onChanged()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {error && <Note tone="error">{error}</Note>}
      <h3 className="mb-2 text-sm font-semibold text-zinc-800">{t("Open requests")}</h3>
      {rows === null ? (
        <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-zinc-400">{t("No open requests for this room.")}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((x) => (
            <li key={x.name} className="rounded-xl border border-zinc-200 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-zinc-800">{x.subject}</span>
                <Badge tone={x.status === "In Progress" ? "sky" : "amber"}>{t(x.status)}</Badge>
                {x.overdue && <Badge tone="rose">{t("Overdue")}</Badge>}
              </div>
              <div className="mt-0.5 text-xs text-zinc-500">
                {t(x.category)} · {t(x.priority)}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {x.status === "Open" && (
                  <Button
                    variant="outline"
                    className="min-h-11"
                    disabled={busy}
                    onClick={() =>
                      act(() => call("kamra.api.advance_ticket", { ticket: x.name, status: "In Progress" }))
                    }
                  >
                    {t("Start")}
                  </Button>
                )}
                <Button
                  className="min-h-11"
                  disabled={busy}
                  onClick={() =>
                    act(() => call("kamra.api.advance_ticket", { ticket: x.name, status: "Resolved" }))
                  }
                >
                  {t("Done")}
                </Button>
                <Button
                  variant="ghost"
                  className="min-h-11"
                  disabled={busy}
                  onClick={() =>
                    act(() => call("kamra.api.advance_ticket", { ticket: x.name, status: "Cancelled" }))
                  }
                >
                  {t("Cancel request")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <h3 className="mb-2 mt-6 text-sm font-semibold text-zinc-800">{t("New request")}</h3>
      <div className="space-y-3 rounded-xl border border-zinc-200 p-3">
        <label className="block text-sm text-zinc-600">
          {t("What does the guest need?")}
          <input
            value={form.subject}
            onChange={(e) => setForm({ ...form, subject: e.target.value })}
            placeholder={t("Extra towels, AC not cooling…")}
            className={cn(inputCls, "mt-1")}
          />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm text-zinc-600">
            {t("Team")}
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className={cn(inputCls, "mt-1")}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(c)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-zinc-600">
            {t("Priority")}
            <select
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
              className={cn(inputCls, "mt-1")}
            >
              {PRIORITIES.map((c) => (
                <option key={c} value={c}>
                  {t(c)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Button
          className="min-h-11 px-4"
          disabled={busy || !form.subject.trim()}
          onClick={() =>
            act(async () => {
              await call("kamra.api.create_ticket", {
                property: d.room.property,
                subject: form.subject.trim(),
                category: form.category,
                priority: form.priority,
                room: d.room.name,
                reservation: d.stay?.name,
                guest: d.stay?.guest,
              })
              setForm({ ...form, subject: "" })
            })
          }
        >
          {t("Add request")}
        </Button>
      </div>
      <p className="mt-3 text-xs text-zinc-400">
        <Link to="/tickets" className="text-brand-700 hover:underline">
          {t("All guest requests")}
        </Link>
      </p>
    </div>
  )
}

// --- Folio and billing ------------------------------------------------------

interface FolioRow {
  name: string
  folio_type: string
  status: string
  grand_total: number
  payments_total: number
  balance: number
}

interface FolioDoc {
  name: string
  charges: { name: string; posting_date: string; charge_type: string; description: string; total: number; amount: number }[]
  payments: { name: string; posting_date: string; mode: string; amount: number; payment_kind?: string }[]
}

export function StayBilling({ d, onChanged }: { d: RoomDetail; onChanged: () => void }) {
  const { t } = useT()
  const loc = useLocale()
  const stay = d.stay!
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const [folios, setFolios] = useState<FolioRow[] | null>(null)
  const [guest, setGuest] = useState<FolioDoc | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rates, setRates] = useState<number[]>(locale().tax_rates)
  const [charge, setCharge] = useState({
    charge_type: "Food & Beverage",
    description: "",
    amount: "",
    gst_rate: "0",
    is_alcohol: false,
  })
  const [pay, setPay] = useState({ folio: "", mode: locale().payment_modes[0] ?? "Cash", amount: "", reference: "" })

  useEffect(() => {
    loadLocale().then((l) => setRates(l.tax_rates))
  }, [])

  const load = useCallback(() => {
    Promise.all([
      call<FolioRow[]>("kamra.api.reservation_folios", { reservation: stay.name }),
      call<FolioDoc | null>("kamra.api.get_folio", { reservation: stay.name }),
    ])
      .then(([rows, g]) => {
        setFolios(rows)
        setGuest(g)
        const open = rows.find((r) => r.status === "Open" && r.folio_type === "Guest") ?? rows[0]
        setPay((p) => ({
          ...p,
          folio: p.folio || open?.name || "",
          amount: p.amount || (open && open.balance > 0 ? String(open.balance) : ""),
        }))
      })
      .catch((e) => setError(serverError(e)))
  }, [stay.name])
  useEffect(load, [load])

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true)
    setError(null)
    setOk(null)
    try {
      if (pinStatus?.required) await ensureUnlocked()
      await fn()
      setOk(done)
      load()
      onChanged()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const lines = [
    ...(guest?.charges ?? []).map((c) => ({
      key: c.name,
      date: c.posting_date,
      label: c.description || t(c.charge_type),
      amount: Number(c.total || c.amount || 0),
      pay: false,
    })),
    ...(guest?.payments ?? []).map((p) => ({
      key: p.name,
      date: p.posting_date,
      label: `${t(p.payment_kind || "Payment")} · ${p.mode}`,
      amount: Number(p.amount || 0),
      pay: true,
    })),
  ]
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, 8)

  return (
    <div>
      {error && (
        <Note tone="error">
          {error}{" "}
          {/till|session|cashier/i.test(error) && (
            <Link to="/cashier" className="font-medium underline">
              {t("Open the till")}
            </Link>
          )}
        </Note>
      )}
      {ok && <Note tone="ok">{ok}</Note>}

      <h3 className="mb-2 text-sm font-semibold text-zinc-800">{t("Folios")}</h3>
      {folios === null ? (
        <p className="text-sm text-zinc-400">{t("Loading…")}</p>
      ) : folios.length === 0 ? (
        <p className="text-sm text-zinc-400">{t("No folio yet.")}</p>
      ) : (
        <ul className="space-y-2">
          {folios.map((f) => (
            <li
              key={f.name}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-200 px-3 py-2"
            >
              <span className="min-w-0">
                <span className="block font-medium text-zinc-800">
                  {t("{type} folio", { type: t(f.folio_type) })}
                  {f.status === "Closed" && ` · ${t("Closed")}`}
                </span>
                <span className="block text-xs text-zinc-500">
                  {t("Bill {total} · paid {paid}", {
                    total: fmtMoney(f.grand_total),
                    paid: fmtMoney(f.payments_total),
                  })}
                </span>
              </span>
              <span className="flex items-center gap-3">
                <span
                  className={cn(
                    "tabular-nums text-base font-semibold",
                    f.balance > 0 ? "text-amber-700" : "text-zinc-700",
                  )}
                >
                  {fmtMoney(f.balance)}
                </span>
                <Link
                  to={`/billing/${encodeURIComponent(f.name)}`}
                  className="inline-flex min-h-11 items-center rounded-lg px-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
                >
                  {t("Open full folio")}
                </Link>
              </span>
            </li>
          ))}
        </ul>
      )}

      {lines.length > 0 && (
        <>
          <h3 className="mb-2 mt-5 text-sm font-semibold text-zinc-800">{t("Recent lines")}</h3>
          <ul className="divide-y divide-zinc-100 text-sm">
            {lines.map((l) => (
              <li key={l.key} className="flex items-center justify-between gap-3 py-1.5">
                <span className="min-w-0 truncate text-zinc-700">
                  <span className="me-2 text-xs tabular-nums text-zinc-400">{l.date}</span>
                  {l.label}
                </span>
                <span className={cn("shrink-0 tabular-nums", l.pay ? "text-emerald-700" : "text-zinc-800")}>
                  {l.pay ? "-" : ""}
                  {fmtMoney(l.amount)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="mb-2 mt-6 text-sm font-semibold text-zinc-800">{t("Post a charge")}</h3>
      <div className="space-y-3 rounded-xl border border-zinc-200 p-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm text-zinc-600">
            {t("Type")}
            <select
              value={charge.charge_type}
              onChange={(e) => setCharge({ ...charge, charge_type: e.target.value })}
              className={cn(inputCls, "mt-1")}
            >
              {CHARGE_TYPES.map((c) => (
                <option key={c} value={c}>
                  {t(c)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-zinc-600">
            {t("Amount (before tax)")}
            <input
              inputMode="decimal"
              value={charge.amount}
              onChange={(e) => setCharge({ ...charge, amount: e.target.value })}
              className={cn(inputCls, "mt-1")}
            />
          </label>
          <label className="block text-sm text-zinc-600">
            {t("What for")}
            <input
              value={charge.description}
              onChange={(e) => setCharge({ ...charge, description: e.target.value })}
              placeholder={t("Two club sandwiches")}
              className={cn(inputCls, "mt-1")}
            />
          </label>
          <label className="block text-sm text-zinc-600">
            {t("{tax} rate", { tax: loc.tax_label || t("Tax") })}
            <select
              value={charge.gst_rate}
              onChange={(e) => setCharge({ ...charge, gst_rate: e.target.value })}
              className={cn(inputCls, "mt-1")}
            >
              {rates.map((r) => (
                <option key={r} value={String(r)}>
                  {r}%
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm text-zinc-600">
          <input
            type="checkbox"
            className="size-5 accent-brand-600"
            checked={charge.is_alcohol}
            onChange={(e) => setCharge({ ...charge, is_alcohol: e.target.checked })}
          />
          {t("Alcohol")}
        </label>
        <p className="text-xs text-zinc-400">
          {t("The hotel's billing rules pick the folio, and food and drink take the hotel's food tax rate.")}
        </p>
        <Button
          className="min-h-11 px-4"
          disabled={busy || !(Number(charge.amount) > 0) || !charge.description.trim()}
          onClick={() =>
            act(async () => {
              await call("kamra.api.post_stay_charge", {
                reservation: stay.name,
                charge_type: charge.charge_type,
                description: charge.description.trim(),
                amount: Number(charge.amount),
                gst_rate: Number(charge.gst_rate),
                is_alcohol: charge.is_alcohol ? 1 : 0,
              })
              setCharge({ ...charge, description: "", amount: "", is_alcohol: false })
            }, t("Charge posted."))
          }
        >
          {t("Post charge")}
        </Button>
      </div>

      <h3 className="mb-2 mt-6 text-sm font-semibold text-zinc-800">{t("Take a payment")}</h3>
      <div className="space-y-3 rounded-xl border border-zinc-200 p-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(folios?.length ?? 0) > 1 && (
            <label className="block text-sm text-zinc-600 sm:col-span-2">
              {t("Folio")}
              <select
                value={pay.folio}
                onChange={(e) => setPay({ ...pay, folio: e.target.value })}
                className={cn(inputCls, "mt-1")}
              >
                {(folios ?? []).map((f) => (
                  <option key={f.name} value={f.name}>
                    {t("{type} folio", { type: t(f.folio_type) })} · {fmtMoney(f.balance)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="block text-sm text-zinc-600">
            {t("How")}
            <select
              value={pay.mode}
              onChange={(e) => setPay({ ...pay, mode: e.target.value })}
              className={cn(inputCls, "mt-1")}
            >
              {loc.payment_modes.map((m) => (
                <option key={m} value={m}>
                  {t(m)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-zinc-600">
            {t("Amount")}
            <input
              inputMode="decimal"
              value={pay.amount}
              onChange={(e) => setPay({ ...pay, amount: e.target.value })}
              className={cn(inputCls, "mt-1")}
            />
          </label>
          <label className="block text-sm text-zinc-600 sm:col-span-2">
            {t("Reference (optional)")}
            <input
              value={pay.reference}
              onChange={(e) => setPay({ ...pay, reference: e.target.value })}
              className={cn(inputCls, "mt-1")}
            />
          </label>
        </div>
        <Button
          className="min-h-11 px-4"
          disabled={busy || !pay.folio || !(Number(pay.amount) > 0)}
          onClick={() =>
            act(async () => {
              await call("kamra.api.add_folio_payment", {
                folio: pay.folio,
                mode: pay.mode,
                kind: "Payment",
                amount: Number(pay.amount),
                reference: pay.reference || undefined,
              })
              setPay({ ...pay, amount: "", reference: "" })
            }, t("Payment recorded."))
          }
        >
          {t("Record payment")}
        </Button>
      </div>
    </div>
  )
}
