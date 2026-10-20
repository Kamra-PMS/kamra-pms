import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Check,
  ExternalLink,
  Lightbulb,
  Loader2,
  Sparkles,
} from "lucide-react"
import { call } from "../lib/api"
import { checkOutWithCredit } from "./CreditCheckout"
import { useCashierAuth } from "../lib/cashierAuth"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { Sheet } from "./ui/sheet"

/* Guided check-out: review bills → settle → guest-moment SOP → confirm.
   Amounts and blockers come from kamra.api.checkout_context; check_out
   remains the single write that flips status. */

interface ChargeLine {
  name: string
  charge_type: string
  description: string
  amount: number
  gst_amount: number
  is_alcohol: number
  group: string
  folio: string
  folio_type: string
}

interface FolioRow {
  name: string
  folio_type: string
  status: string
  balance: number
  grand_total: number
  paid_total: number
  invoice_number: string | null
  charges: ChargeLine[]
  can_city_ledger: boolean
}

interface SopStep {
  step_key: string
  step_type: string
  title: string
  instruction: string
  prompt_to_guest: string
  is_blocking: number
  sequence: number
  state: "done" | "blocked" | "todo"
  tip: string
}

export interface CheckoutContext {
  reservation: {
    name: string
    status: string
    guest: string | null
    guest_name: string
    company: string | null
    company_name: string | null
    room: string | null
    room_number: string | null
    room_type_name: string | null
    check_in_date: string
    check_out_date: string
    adults: number
    children: number
    vip: 0 | 1
    group_booking?: string | null
  }
  currency_symbol: string
  folios: FolioRow[]
  companions?: {
    name: string
    guest_name: string
    room_number?: string | null
    check_out_date?: string
  }[]
  groups: Record<
    string,
    { group: string; amount: number; count: number; lines: ChargeLine[] }
  >
  totals: {
    charges: number
    paid: number
    balance: number
    owed: number
    refund_due: number
    city_ledger_eligible: number
  }
  billing: {
    company: string | null
    company_name: string | null
    credit_allowed: boolean
    rules: { charge_type: string; pay_by: string }[]
  }
  deposit: {
    name: string
    status: string
    required_amount: number
    collected_amount: number
    withheld_amount: number
    refunded_amount: number
    balance: number
    reason: string
  } | null
  blockers: { code: string; message: string; amount: number }[]
  actions: {
    can_checkout: boolean
    can_collect: boolean
    can_city_ledger: boolean
    can_refund_deposit: boolean
    can_withhold_deposit: boolean
  }
  sop: {
    name: string | null
    key: string
    title: string
    steps: SopStep[]
    next_tip: string | null
  }
  /** True only when the property has AI enabled + a key. Tips work without it. */
  ai_tips_available?: boolean
}

const STEPS = ["review", "settle", "guest", "confirm"] as const
type WizardStep = (typeof STEPS)[number]

const fmt = (n: number, symbol?: string) =>
  `${symbol ?? cur()}${Number(n || 0).toLocaleString(moneyLocale(), {
    maximumFractionDigits: 2,
  })}`

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const GROUP_ORDER = [
  "Room",
  "Restaurant",
  "Laundry",
  "Spa",
  "Damages",
  "Discounts",
  "Extras",
]

function TipBanner({ tip, ai }: { tip: string | null; ai?: boolean }) {
  const { t } = useT()
  if (!tip) return null
  return (
    <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
      {ai ? (
        <Sparkles className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
      ) : (
        <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
      )}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
          {t("Next")}
        </p>
        <p>{tip}</p>
      </div>
    </div>
  )
}

function StateChip({ state }: { state: SopStep["state"] }) {
  const { t } = useT()
  const tone =
    state === "done"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : state === "blocked"
        ? "border-rose-200 bg-rose-50 text-rose-800"
        : "border-zinc-200 bg-zinc-50 text-zinc-600"
  const label =
    state === "done" ? t("Done") : state === "blocked" ? t("Blocked") : t("To do")
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", tone)}>
      {label}
    </span>
  )
}

export default function CheckOutDialog(props: {
  reservation: string
  onDone: () => void
  onClose: () => void
  /** Open another stay's check-out (group companions). */
  onOpenReservation?: (reservation: string) => void
}) {
  const { t } = useT()
  const loc = useLocale()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const [ctx, setCtx] = useState<CheckoutContext | null>(null)
  const [step, setStep] = useState<WizardStep>("review")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [creditOverride, setCreditOverride] = useState("")
  const [needsCreditOverride, setNeedsCreditOverride] = useState(false)
  const [aiTip, setAiTip] = useState<string | null>(null)
  const [confirmedSteps, setConfirmedSteps] = useState<Record<string, boolean>>({})
  const [payAmount, setPayAmount] = useState("")
  const [payMode, setPayMode] = useState(loc.payment_modes[0] ?? "Cash")
  const [payRef, setPayRef] = useState("")
  const [payFolio, setPayFolio] = useState("")
  const [withholdAmt, setWithholdAmt] = useState("")
  const [withholdReason, setWithholdReason] = useState("")

  const load = useCallback(async () => {
    setError(null)
    try {
      const c = await call<CheckoutContext>("kamra.api.checkout_context", {
        reservation: props.reservation,
      })
      setCtx(c)
      setNeedsCreditOverride(false)
      setCreditOverride("")
      const guestFolio =
        c.folios.find((f) => f.folio_type === "Guest" && f.balance > 0.009) ||
        c.folios.find((f) => f.balance > 0.009) ||
        c.folios[0]
      setPayFolio(guestFolio?.name || "")
      setPayAmount(
        c.totals.owed > 0.009
          ? String(c.totals.owed)
          : c.totals.balance > 0.009
            ? String(c.totals.balance)
            : "",
      )
      if (c.deposit?.balance) setWithholdAmt(String(c.deposit.balance))
      setAiTip(null)
    } catch (e) {
      setError(serverError(e))
    }
  }, [props.reservation])

  useEffect(() => {
    load()
  }, [load])

  const tip = aiTip || ctx?.sop.next_tip || null
  const stepIndex = STEPS.indexOf(step)

  const guestSteps = useMemo(
    () =>
      (ctx?.sop.steps || []).filter((s) =>
        ["ask_guest", "confirm"].includes(s.step_type),
      ),
    [ctx],
  )

  const blockingUnresolved = useMemo(() => {
    if (!ctx) return true
    if (!ctx.actions.can_checkout) return true
    return (ctx.sop.steps || []).some(
      (s) => s.is_blocking && s.state === "blocked",
    )
  }, [ctx])

  async function collectPayment() {
    if (!payFolio || !payAmount) return
    setBusy(true)
    setError(null)
    try {
      if (pinStatus?.required) await ensureUnlocked()
      await call("kamra.api.add_folio_payment", {
        folio: payFolio,
        mode: payMode,
        amount: Number(payAmount),
        reference: payRef.trim() || undefined,
        kind: "Payment",
      })
      setPayRef("")
      await load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function sendCityLedger(folio: string) {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.ledger.city_ledger_transfer", {
        folio,
        company: ctx?.billing.company || undefined,
      })
      await load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function refundDeposit() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.refund_security_deposit", {
        reservation: props.reservation,
      })
      await load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function withholdDeposit() {
    if (!withholdAmt || !withholdReason.trim()) return
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.withhold_security_deposit", {
        reservation: props.reservation,
        amount: Number(withholdAmt),
        reason: withholdReason.trim(),
      })
      setWithholdReason("")
      await load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function doCheckOut() {
    if (blockingUnresolved) return
    setBusy(true)
    setError(null)
    try {
      await checkOutWithCredit(
        props.reservation,
        needsCreditOverride ? creditOverride.trim() || undefined : undefined,
      )
      props.onDone()
    } catch (e) {
      const msg = serverError(e)
      if (msg.includes("CREDIT_BLOCKED")) {
        setNeedsCreditOverride(true)
        setError(
          msg.replace(/^CREDIT_BLOCKED:\s*/, "") ||
            "Company credit is blocked — enter an override reason to continue.",
        )
      } else {
        setError(msg)
      }
      setBusy(false)
      await load()
    }
  }

  const r = ctx?.reservation
  const symbol = ctx?.currency_symbol

  function footer() {
    return (
      <div className="flex w-full flex-col gap-2">
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={props.onClose}>
            {t("Cancel")}
          </Button>
          <div className="ml-auto flex items-center gap-2">
            {stepIndex > 0 && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => setStep(STEPS[stepIndex - 1])}
              >
                {t("Back")}
              </Button>
            )}
            {step !== "confirm" ? (
              <Button
                disabled={busy || !ctx || (step === "settle" && blockingUnresolved)}
                onClick={() => setStep(STEPS[stepIndex + 1])}
              >
                {step === "settle" && blockingUnresolved
                  ? t("Settle to continue")
                  : t("Continue")}
              </Button>
            ) : (
              <Button
                disabled={
                  busy ||
                  !ctx ||
                  blockingUnresolved ||
                  (needsCreditOverride && !creditOverride.trim())
                }
                onClick={doCheckOut}
              >
                {busy ? t("Checking out…") : t("Confirm check-out")}
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <Sheet
      wide
      title={
        r
          ? t("Check out {name}", { name: r.guest_name })
          : t("Check out")
      }
      description={
        r
          ? `${r.room_number ? t("Room {n}", { n: r.room_number }) + " · " : ""}${r.room_type_name ?? ""} · ${r.check_in_date} → ${r.check_out_date}`
          : undefined
      }
      onClose={props.onClose}
      footer={footer()}
    >
      {!ctx && !error && (
        <p className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {t("Loading bill…")}
        </p>
      )}
      {ctx && r && (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-1.5">
            {STEPS.map((s, i) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  if (i <= stepIndex || (s !== "confirm" && s !== "guest") || !blockingUnresolved)
                    setStep(s)
                }}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium",
                  step === s
                    ? "border-brand-400 bg-brand-50 text-brand-800"
                    : "border-zinc-200 text-zinc-500",
                )}
              >
                {i + 1}.{" "}
                {s === "review"
                  ? t("Review")
                  : s === "settle"
                    ? t("Settle")
                    : s === "guest"
                      ? t("Guest moment")
                      : t("Confirm")}
              </button>
            ))}
          </div>

          <TipBanner tip={tip} ai={Boolean(aiTip)} />

          {step === "review" && (
            <div className="space-y-4">
              <section className="rounded-xl border border-zinc-200 p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold text-zinc-800">
                    {t("Stay summary")}
                  </h3>
                  <p className="text-sm tabular-nums text-zinc-600">
                    {t("Balance {amount}", {
                      amount: fmt(ctx.totals.balance, symbol),
                    })}
                  </p>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-zinc-400">{t("Charges")}</dt>
                    <dd className="font-medium tabular-nums">
                      {fmt(ctx.totals.charges, symbol)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-400">{t("Paid")}</dt>
                    <dd className="font-medium tabular-nums">
                      {fmt(ctx.totals.paid, symbol)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-400">{t("Owed")}</dt>
                    <dd className="font-medium tabular-nums text-rose-700">
                      {fmt(ctx.totals.owed, symbol)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-400">{t("Refund due")}</dt>
                    <dd className="font-medium tabular-nums text-amber-700">
                      {fmt(ctx.totals.refund_due, symbol)}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-xl border border-zinc-200 p-4">
                <h3 className="mb-2 text-sm font-semibold text-zinc-800">
                  {t("Billing instructions")}
                </h3>
                {ctx.billing.company ? (
                  <div className="space-y-1 text-sm text-zinc-700">
                    <p>
                      {t("Company")}:{" "}
                      <span className="font-medium">
                        {ctx.billing.company_name || ctx.billing.company}
                      </span>
                      {ctx.billing.credit_allowed ? (
                        <span className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800">
                          {t("Credit allowed")}
                        </span>
                      ) : null}
                    </p>
                    {ctx.billing.rules.length ? (
                      <ul className="mt-1 space-y-0.5 text-xs text-zinc-600">
                        {ctx.billing.rules.map((rule) => (
                          <li key={rule.charge_type}>
                            {t(rule.charge_type)} → {t(rule.pay_by)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-zinc-500">
                        {t("No charge-type rules — confirm bill-to with the guest.")}
                      </p>
                    )}
                    <p className="text-xs text-zinc-500">
                      {t("Alcohol always bills the guest.")}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-zinc-600">
                    {t("Guest pays the bill (no company on this stay).")}
                  </p>
                )}
              </section>

              {GROUP_ORDER.filter((g) => ctx.groups[g]).map((g) => {
                const grp = ctx.groups[g]
                return (
                  <section
                    key={g}
                    className="rounded-xl border border-zinc-200 p-4"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-zinc-800">
                        {t(g)}
                      </h3>
                      <span className="text-sm font-medium tabular-nums">
                        {fmt(grp.amount, symbol)}
                      </span>
                    </div>
                    <ul className="divide-y divide-zinc-100 text-sm">
                      {grp.lines.map((line) => (
                        <li
                          key={line.name}
                          className="flex items-start justify-between gap-3 py-1.5"
                        >
                          <span className="text-zinc-700">
                            <span className="font-medium">
                              {t(line.charge_type)}
                            </span>
                            {line.description ? (
                              <span className="text-zinc-500">
                                {" "}
                                — {line.description}
                              </span>
                            ) : null}
                            {line.is_alcohol ? (
                              <span className="ml-1 text-[10px] font-semibold uppercase text-rose-600">
                                {t("Guest only")}
                              </span>
                            ) : null}
                            <span className="ml-1 text-xs text-zinc-400">
                              ({line.folio_type})
                            </span>
                          </span>
                          <span className="shrink-0 tabular-nums text-zinc-800">
                            {fmt(line.amount + line.gst_amount, symbol)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )
              })}

              {ctx.folios.map((f) => (
                <div
                  key={f.name}
                  className="flex items-center justify-between text-xs text-zinc-500"
                >
                  <span>
                    {t("{type} folio", { type: t(f.folio_type) })} · {f.name}
                  </span>
                  <a
                    href={toFullPath(`/billing/${encodeURIComponent(f.name)}`)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
                  >
                    {t("Open folio")}
                    <ExternalLink className="size-3" aria-hidden />
                  </a>
                </div>
              ))}
            </div>
          )}

          {step === "settle" && (
            <div className="space-y-4">
              {ctx.blockers.length > 0 && (
                <ul className="space-y-1 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  {ctx.blockers.map((b) => (
                    <li key={b.code}>{b.message}</li>
                  ))}
                </ul>
              )}
              {!ctx.blockers.length && (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                  <Check className="mr-1 inline size-4" aria-hidden />
                  {t("Balances are clear — you can continue.")}
                </p>
              )}

              {(ctx.actions.can_collect || ctx.totals.owed > 0.009) && (
                <section className="rounded-xl border border-zinc-200 p-4">
                  <h3 className="mb-2 text-sm font-semibold text-zinc-800">
                    {t("Collect payment")}
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Folio")}</span>
                      <select
                        className={inputCls}
                        value={payFolio}
                        onChange={(e) => setPayFolio(e.target.value)}
                      >
                        {ctx.folios.map((f) => (
                          <option key={f.name} value={f.name}>
                            {f.folio_type} · {fmt(f.balance, symbol)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Mode")}</span>
                      <select
                        className={inputCls}
                        value={payMode}
                        onChange={(e) => setPayMode(e.target.value)}
                      >
                        {loc.payment_modes.map((m) => (
                          <option key={m} value={m}>
                            {t(m)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Amount")}</span>
                      <input
                        className={inputCls}
                        type="number"
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                      />
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">
                        {t("Reference (optional)")}
                      </span>
                      <input
                        className={inputCls}
                        value={payRef}
                        onChange={(e) => setPayRef(e.target.value)}
                      />
                    </label>
                  </div>
                  <Button
                    className="mt-3"
                    disabled={busy || !payAmount || !payFolio}
                    onClick={collectPayment}
                  >
                    {t("Record payment")}
                  </Button>
                </section>
              )}

              {ctx.actions.can_city_ledger && (
                <section className="rounded-xl border border-sky-200 bg-sky-50/50 p-4">
                  <h3 className="mb-1 text-sm font-semibold text-sky-900">
                    {t("City ledger")}
                  </h3>
                  <p className="mb-3 text-sm text-sky-800">
                    {t(
                      "{amount} can move to {company}'s city ledger (credit allowed).",
                      {
                        amount: fmt(ctx.totals.city_ledger_eligible, symbol),
                        company:
                          ctx.billing.company_name || ctx.billing.company || "",
                      },
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {ctx.folios
                      .filter((f) => f.can_city_ledger)
                      .map((f) => (
                        <Button
                          key={f.name}
                          variant="outline"
                          disabled={busy}
                          onClick={() => sendCityLedger(f.name)}
                        >
                          {t("Transfer {type}", { type: t(f.folio_type) })}
                        </Button>
                      ))}
                  </div>
                </section>
              )}

              {ctx.deposit && (
                <section className="rounded-xl border border-zinc-200 p-4">
                  <h3 className="mb-1 text-sm font-semibold text-zinc-800">
                    {t("Security deposit")}
                  </h3>
                  <p className="text-sm text-zinc-600">
                    {t("Status")}: {t(ctx.deposit.status)} ·{" "}
                    {t("Held {held}, refundable {bal}", {
                      held: fmt(ctx.deposit.collected_amount, symbol),
                      bal: fmt(ctx.deposit.balance, symbol),
                    })}
                  </p>
                  {ctx.actions.can_withhold_deposit && (
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <input
                        className={inputCls}
                        type="number"
                        placeholder={t("Withhold amount")}
                        value={withholdAmt}
                        onChange={(e) => setWithholdAmt(e.target.value)}
                      />
                      <input
                        className={inputCls}
                        placeholder={t("Damage reason")}
                        value={withholdReason}
                        onChange={(e) => setWithholdReason(e.target.value)}
                      />
                      <Button
                        variant="outline"
                        disabled={busy || !withholdAmt || !withholdReason.trim()}
                        onClick={withholdDeposit}
                      >
                        {t("Withhold for damage")}
                      </Button>
                    </div>
                  )}
                  {ctx.actions.can_refund_deposit && (
                    <Button
                      className="mt-3"
                      variant="outline"
                      disabled={busy}
                      onClick={refundDeposit}
                    >
                      {t("Refund deposit {amount}", {
                        amount: fmt(ctx.deposit.balance, symbol),
                      })}
                    </Button>
                  )}
                </section>
              )}

              <p className="text-xs text-zinc-500">
                {t(
                  "For splits, allowances, or complex adjustments, open the folio — then come back here.",
                )}{" "}
                {ctx.folios[0] && (
                  <a
                    href={toFullPath(
                      `/billing/${encodeURIComponent(ctx.folios[0].name)}`,
                    )}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {t("Open folio")}
                  </a>
                )}
              </p>

              <Button variant="outline" disabled={busy} onClick={load}>
                {t("Refresh balances")}
              </Button>
            </div>
          )}

          {step === "guest" && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-600">
                {t(
                  "Walk these guest-facing steps. Tick each one as you go — they are your property's checkout SOP.",
                )}
              </p>
              {(guestSteps.length
                ? guestSteps
                : ctx.sop.steps.filter((s) =>
                    ["ask_feedback", "farewell", "verify_restaurant", "confirm_discounts", "confirm_bill_to"].includes(
                      s.step_key,
                    ),
                  )
              ).map((s) => {
                const done = confirmedSteps[s.step_key] || s.state === "done"
                return (
                  <button
                    key={s.step_key || s.title}
                    type="button"
                    onClick={() =>
                      setConfirmedSteps((prev) => ({
                        ...prev,
                        [s.step_key]: !prev[s.step_key],
                      }))
                    }
                    className={cn(
                      "flex w-full items-start gap-3 rounded-xl border p-3 text-left transition",
                      done
                        ? "border-emerald-200 bg-emerald-50/60"
                        : "border-zinc-200 hover:border-brand-300",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
                        done
                          ? "border-emerald-500 bg-emerald-500 text-white"
                          : "border-zinc-300",
                      )}
                    >
                      {done ? <Check className="size-3" aria-hidden /> : null}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-zinc-800">
                          {t(s.title)}
                        </span>
                        <StateChip state={s.state} />
                      </span>
                      {s.prompt_to_guest ? (
                        <span className="mt-1 block text-sm italic text-zinc-600">
                          “{s.prompt_to_guest}”
                        </span>
                      ) : (
                        <span className="mt-1 block text-sm text-zinc-600">
                          {s.tip || s.instruction}
                        </span>
                      )}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {step === "confirm" && (
            <div className="space-y-4">
              <section className="rounded-xl border border-zinc-200 p-4">
                <h3 className="mb-2 text-sm font-semibold text-zinc-800">
                  {t("Ready to check out")}
                </h3>
                <ul className="space-y-1 text-sm text-zinc-700">
                  <li>
                    {r.guest_name}
                    {r.room_number
                      ? ` · ${t("Room {n}", { n: r.room_number })}`
                      : ""}
                  </li>
                  <li>
                    {t("Balance")}: {fmt(ctx.totals.balance, symbol)}
                  </li>
                  {ctx.actions.can_city_ledger && (
                    <li className="text-sky-800">
                      {t(
                        "Remaining {amount} will move to the city ledger on confirm.",
                        {
                          amount: fmt(ctx.totals.city_ledger_eligible, symbol),
                        },
                      )}
                    </li>
                  )}
                  {ctx.deposit && ctx.deposit.balance > 0.009 && (
                    <li className="text-amber-800">
                      {t("Deposit still refundable: {amount}", {
                        amount: fmt(ctx.deposit.balance, symbol),
                      })}
                    </li>
                  )}
                </ul>
              </section>
              {(ctx.companions?.length ?? 0) > 0 && (
                <section className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <h3 className="mb-2 text-sm font-semibold text-amber-900">
                    {t("Other guests still in-house on this group")}
                  </h3>
                  <p className="mb-2 text-xs text-amber-800">
                    {t(
                      "This checks out only {name}. Open each guest below when they are ready.",
                      { name: r.guest_name },
                    )}
                  </p>
                  <ul className="space-y-1.5 text-sm text-amber-950">
                    {ctx.companions!.map((c) => (
                      <li key={c.name} className="flex items-center justify-between gap-2">
                        <span>
                          {c.guest_name}
                          {c.room_number
                            ? ` · ${t("Room {n}", { n: c.room_number })}`
                            : ""}
                        </span>
                        <button
                          type="button"
                          className="shrink-0 text-sm font-medium text-brand-700 hover:underline"
                          onClick={() => {
                            if (props.onOpenReservation) {
                              props.onOpenReservation(c.name)
                            }
                          }}
                        >
                          {t("Check out")}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {needsCreditOverride && (
                <label className="block">
                  <span className="mb-1 block text-sm text-zinc-600">
                    {t("Reason for company credit override (logged with your name)")}
                  </span>
                  <textarea
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                    rows={3}
                    maxLength={500}
                    value={creditOverride}
                    onChange={(e) => setCreditOverride(e.target.value)}
                    autoFocus
                  />
                </label>
              )}
              {blockingUnresolved ? (
                <p className="text-sm text-rose-700">
                  {t("Resolve outstanding balances before confirming check-out.")}
                </p>
              ) : (
                <p className="text-sm text-emerald-700">
                  {t(
                    "Confirming marks the stay Checked Out, dirties the room, and queues a checkout clean.",
                  )}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </Sheet>
  )
}
