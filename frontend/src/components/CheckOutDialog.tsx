import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { Check, ExternalLink, Lightbulb, Loader2, Printer, TriangleAlert } from "lucide-react"
import { call } from "../lib/api"
import { checkOutWithCredit } from "./CreditCheckout"
import { useCashierAuth } from "../lib/cashierAuth"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { moneyLocale, useLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { Sheet } from "./ui/sheet"
import { StepFlowFooter, StepFlowHeader, useStepFlow, type FlowStep } from "./StepFlow"

/* Guided check-out, one stay at a time:
     Bill (folios, lines, bills not on the folio yet)
     -> Late check-out (only when the guest leaves after check-out time)
     -> Company bill (only when a company pays: what goes to its account,
        and the credit check)
     -> Payment (collect what is owed or refund what is due; a held
        security deposit goes back through its own refund)
     -> Guest moment (the property's SOP, optional)
     -> Check out
     -> Invoice (close each folio and issue its invoice, print links).
   Every number and refusal comes from kamra.api.checkout_context, which
   writes nothing; each button calls the one existing endpoint for that
   action, and check_out stays the only write that departs the guest.
   The invoice comes after check-out on purpose: check-out may still post
   the last night and move the company's share to the city ledger, and a
   folio invoiced before that is frozen and stops the check-out. */

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
  folio: string
  name: string
  folio_type: string
  status: string
  invoice_number: string | null
  balance: number
  grand_total: number
  paid_total: number
  refundable: number
  city_ledger_company: string | null
  side: "guest" | "company" | "group"
  has_charges: boolean
  charges: ChargeLine[]
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

interface CreditCheck {
  ok: boolean
  blocked: boolean
  company: string
  amount: number
  reasons: string[]
}

interface PendingBill {
  kind: "pos" | "laundry"
  name: string
  label: string
  status: string
  amount: number
  complimentary: boolean
  can_post_to_room: boolean
  pay_modes: string[]
}

interface Blocker {
  code: string
  step: string
  message: string
  folio?: string | null
  can_override?: boolean
}

interface RefundAction {
  kind: "deposit" | "folio"
  folio: string
  folio_type: string
  amount: number
  source: "security_deposit" | "overpayment"
  mode: string
}

export interface CheckoutContext {
  reservation: {
    name: string
    status: string
    guest: string | null
    guest_name: string
    company: string | null
    company_name: string | null
    group_booking: string | null
    room: string | null
    room_number: string | null
    room_type_name: string | null
    check_in_date: string
    check_out_date: string
  }
  currency_symbol: string
  payment_modes: string[]
  pin_required: boolean
  till_open: boolean
  folios: FolioRow[]
  groups: Record<string, { group: string; amount: number; count: number; lines: ChargeLine[] }>
  totals: {
    charges: number
    paid: number
    balance: number
    owed: number
    refund_due: number
    to_city_ledger: number
  }
  billing: {
    company: string | null
    company_name: string | null
    rules: { charge_type: string; pay_by: string }[]
  }
  city_ledger: { folio: string; company: string; company_name: string; amount: number }[]
  credit: { checks: CreditCheck[]; ok: boolean; blocked: boolean; can_override: boolean } | null
  deposit: { name: string; status: string; held: number; folio: string | null } | null
  collect: { folio: string; folio_type: string; amount: number; invoiced: boolean }[]
  refunds: RefundAction[]
  pending_bills: PendingBill[]
  late_checkout: {
    checkout_time: string
    now: string
    late: boolean
    requested: boolean
    already_charged: boolean
    folio: string | null
    tax_rate: number
  } | null
  companions: { name: string; guest_name: string; room_number: string | null }[]
  blockers: Blocker[]
  notices: { code: string; message: string }[]
  settled: boolean
  actions: { can_checkout: boolean; can_withhold_deposit: boolean }
  sop: { steps: SopStep[]; next_tip: string | null }
}

type StepKey = "review" | "late" | "company" | "settle" | "guest" | "confirm" | "invoice"

const GROUP_ORDER = ["Room", "Restaurant", "Laundry", "Spa", "Damages", "Discounts", "Extras"]
const EPS = 0.009

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function Section(props: { title: string; tone?: "warn" | "info" | "ok"; children: ReactNode }) {
  return (
    <section
      className={cn(
        "rounded-xl border p-3 sm:p-4",
        props.tone === "warn" && "border-amber-200 bg-amber-50/60",
        props.tone === "info" && "border-sky-200 bg-sky-50/50",
        props.tone === "ok" && "border-emerald-200 bg-emerald-50/60",
        !props.tone && "border-zinc-200",
      )}
    >
      <h3 className="mb-2 text-sm font-semibold text-zinc-800">{props.title}</h3>
      {props.children}
    </section>
  )
}

function Problems(props: { items: Blocker[]; folioLink?: (f: string) => string }) {
  const { t } = useT()
  if (!props.items.length) return null
  return (
    <ul role="alert" className="space-y-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      {props.items.map((b) => (
        <li key={b.code + (b.folio ?? "")} className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {b.message}
            {b.folio && props.folioLink ? (
              <>
                {" "}
                <a href={props.folioLink(b.folio)} target="_blank" rel="noreferrer"
                  className="font-medium underline">
                  {t("Open folio")}
                </a>
              </>
            ) : null}
            {b.code === "till_closed" ? (
              <>
                {" "}
                <a href={toFullPath("/cashier")} target="_blank" rel="noreferrer"
                  className="font-medium underline">
                  {t("Open the till")}
                </a>
              </>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function CheckOutDialog(props: {
  reservation: string
  /** After a check-out: the desk is done (also called on close once checked out). */
  onDone: () => void
  onClose: () => void
  /** Open another stay's check-out (group companions). */
  onOpenReservation?: (reservation: string) => void
}) {
  const { t } = useT()
  const loc = useLocale()
  const { ensureUnlocked } = useCashierAuth()
  const [ctx, setCtx] = useState<CheckoutContext | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [checkedOut, setCheckedOut] = useState(false)
  const [creditWarnings, setCreditWarnings] = useState<string[]>([])
  // per-step desk input
  const [payMode, setPayMode] = useState("")
  const [payRef, setPayRef] = useState("")
  const [refundModes, setRefundModes] = useState<Record<string, string>>({})
  const [refundReason, setRefundReason] = useState("")
  const [withholdAmt, setWithholdAmt] = useState("")
  const [withholdReason, setWithholdReason] = useState("")
  const [lateAmt, setLateAmt] = useState("")
  const [lateDesc, setLateDesc] = useState("")
  const [lateRate, setLateRate] = useState("")
  const [outletModes, setOutletModes] = useState<Record<string, string>>({})
  const [companyOk, setCompanyOk] = useState(false)
  const [override, setOverride] = useState("")
  const [skipped, setSkipped] = useState<Record<string, boolean>>({})
  const [ticked, setTicked] = useState<Record<string, boolean>>({})
  const shown = useRef(new Set<StepKey>())

  const load = useCallback(async () => {
    try {
      const c = await call<CheckoutContext>("kamra.api.checkout_context", {
        reservation: props.reservation,
      })
      setCtx(c)
      setLoadError(null)
      if (c.reservation.status !== "Checked In") setCheckedOut(true)
      return c
    } catch (e) {
      setLoadError(serverError(e))
      return null
    }
  }, [props.reservation])

  useEffect(() => {
    void load()
  }, [load])

  // sensible defaults once the context arrives
  useEffect(() => {
    if (!ctx) return
    setPayMode((m) => m || ctx.payment_modes[0] || "Cash")
    setRefundModes((prev) => {
      const next = { ...prev }
      for (const r of ctx.refunds) next[r.kind + r.folio] ??= r.mode
      return next
    })
    setRefundReason((r) => r || t("Refund of overpayment at check-out"))
    setLateDesc((d) => d || t("Late check-out"))
    if (ctx.late_checkout) setLateRate((r) => r || String(ctx.late_checkout?.tax_rate ?? 0))
  }, [ctx, t])

  const sym = ctx?.currency_symbol ?? ""
  const fmt = (n: number) =>
    `${sym}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`
  const folioLink = (f: string) => toFullPath(`/billing/${encodeURIComponent(f)}`)
  const blockersFor = (step: StepKey) => (ctx?.blockers ?? []).filter((b) => b.step === step &&
    !["owed", "refund"].includes(b.code))

  const settleProblems = blockersFor("settle")
  const reviewProblems = blockersFor("review")
  const credit = ctx?.credit
  const creditBlocked = Boolean(credit?.blocked)
  const guestSteps = (ctx?.sop.steps ?? []).filter((s) => ["ask_guest", "confirm"].includes(s.step_type))
  const inHouse = ctx?.reservation.status === "Checked In"

  const need: Record<StepKey, boolean> = {
    review: true,
    late: Boolean(inHouse && ctx?.late_checkout),
    company: Boolean(inHouse && ((ctx?.city_ledger.length ?? 0) > 0 || credit)),
    settle: Boolean(inHouse && ctx && (ctx.collect.length || ctx.refunds.length ||
      settleProblems.length || !ctx.settled)),
    guest: Boolean(inHouse && guestSteps.length),
    confirm: true,
    invoice: true,
  }
  for (const k of Object.keys(need) as StepKey[]) if (need[k]) shown.current.add(k)

  const settleDone = Boolean(ctx?.settled && !settleProblems.length)
  const steps: FlowStep[] = useMemo(() => {
    const done = (k: StepKey) => checkedOut && k !== "invoice"
    const allInvoiced = Boolean(ctx && ctx.folios.filter((f) => f.side !== "group" && f.has_charges)
      .every((f) => f.status === "Closed"))
    const list: (FlowStep & { key: StepKey })[] = [
      { key: "review", label: t("Bill"),
        status: done("review") ? "done" : reviewProblems.length ? "blocked" : undefined },
      { key: "late", label: t("Late check-out"), optional: true,
        status: done("late") || ctx?.late_checkout?.already_charged ? "done"
          : skipped.late ? "skipped" : undefined },
      { key: "company", label: t("Company bill"),
        status: done("company") || companyOk ? "done"
          : creditBlocked && !credit?.can_override ? "blocked" : undefined },
      { key: "settle", label: t("Payment"),
        status: done("settle") || settleDone ? "done" : settleProblems.length ? "blocked" : undefined },
      { key: "guest", label: t("Guest moment"), optional: true,
        status: done("guest") ? "done" : skipped.guest ? "skipped" : undefined },
      { key: "confirm", label: t("Check out"), status: checkedOut ? "done" : undefined },
      { key: "invoice", label: t("Invoice"), status: allInvoiced && checkedOut ? "done" : undefined },
    ]
    return list.map((s) => ({ ...s, hidden: !shown.current.has(s.key) }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx, checkedOut, skipped, companyOk, settleDone, creditBlocked, t])

  const flow = useStepFlow(steps)
  const current = flow.current as StepKey
  // a stay that is already checked out opens on its invoices
  useEffect(() => {
    if (checkedOut) flow.goTo("invoice")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkedOut])

  async function run(fn: () => Promise<unknown>, money = true) {
    setBusy(true)
    setError(null)
    try {
      if (money && ctx?.pin_required) await ensureUnlocked()
      await fn()
    } catch (e) {
      setError(serverError(e))
    } finally {
      await load()
      setBusy(false)
    }
  }

  const collectTotal = (ctx?.collect ?? []).reduce((s, c) => s + c.amount, 0)
  const refundTotal = (ctx?.refunds ?? []).reduce((s, r) => s + r.amount, 0)

  function collect() {
    return run(async () => {
      for (const c of ctx?.collect ?? []) {
        await call("kamra.api.add_folio_payment", {
          folio: c.folio, mode: payMode, amount: c.amount, kind: "Payment",
          reference: payRef.trim() || undefined,
        })
      }
      setPayRef("")
    })
  }

  function refund() {
    const reason = refundReason.trim()
    return run(async () => {
      for (const r of ctx?.refunds ?? []) {
        const mode = refundModes[r.kind + r.folio] || r.mode
        if (r.kind === "deposit") {
          await call("kamra.api.refund_security_deposit", {
            reservation: props.reservation, amount: r.amount, mode, note: reason,
          })
        } else {
          await call("kamra.api.refund_folio_payment", {
            folio: r.folio, amount: r.amount, mode, reason,
          })
        }
      }
    })
  }

  function withhold() {
    return run(async () => {
      await call("kamra.api.withhold_security_deposit", {
        reservation: props.reservation, amount: Number(withholdAmt), reason: withholdReason.trim(),
      })
      setWithholdAmt("")
      setWithholdReason("")
    })
  }

  function addLateFee() {
    const lc = ctx?.late_checkout
    if (!lc?.folio) return
    return run(async () => {
      await call("kamra.api.add_folio_charge", {
        folio: lc.folio, charge_type: "Late Checkout",
        description: lateDesc.trim() || t("Late check-out"),
        amount: Number(lateAmt), gst_rate: Number(lateRate || 0),
      })
      setLateAmt("")
    }, false)
  }

  function postToRoom(b: PendingBill) {
    return run(async () => {
      if (b.kind === "pos") await call("kamra.pos.deliver_order", { order: b.name })
      else await call("kamra.laundry.deliver_laundry", { order: b.name })
    }, false)
  }

  function payAtOutlet(b: PendingBill) {
    return run(async () => {
      await call("kamra.pos.pay_order", { order: b.name, mode: outletModes[b.name] || b.pay_modes[0] })
    })
  }

  async function doCheckOut() {
    setBusy(true)
    setError(null)
    try {
      const out = await checkOutWithCredit(
        props.reservation,
        creditBlocked && override.trim() ? override.trim() : undefined,
      )
      setCreditWarnings(
        (out.credit_warnings ?? []).filter((w) => !w.overridden)
          .flatMap((w) => w.reasons.map((r) => `${w.company}: ${r}`)),
      )
      setCheckedOut(true)
      await load()
    } catch (e) {
      const msg = serverError(e)
      setError(msg.replace(/^CREDIT_BLOCKED:\s*/, ""))
      await load()
      if (msg.includes("CREDIT_BLOCKED")) flow.goTo("company")
    } finally {
      setBusy(false)
    }
  }

  function invoice(folios: string[]) {
    return run(async () => {
      for (const f of folios) await call("kamra.api.close_folio", { folio: f })
    })
  }

  const close = checkedOut ? props.onDone : props.onClose
  const r = ctx?.reservation

  // ---- footer: what Continue means on each step ----------------------
  let continueLabel: string | undefined
  let continueDisabled = false
  let onContinue: (() => void) | undefined = flow.next
  if (current === "review") continueDisabled = reviewProblems.length > 0
  if (current === "company")
    continueDisabled = !companyOk || (creditBlocked && (!credit?.can_override || !override.trim()))
  if (current === "settle") {
    continueDisabled = !settleDone
    if (!settleDone) continueLabel = t("Settle to continue")
  }
  if (current === "confirm") {
    continueLabel = busy ? t("Checking out…") : t("Check out")
    continueDisabled = checkedOut || !ctx?.actions.can_checkout &&
      !(creditBlocked && credit?.can_override && override.trim() && ctx?.settled)
    onContinue = () => void doCheckOut()
  }
  if (current === "invoice") {
    continueLabel = t("Finish")
    continueDisabled = !checkedOut
    onContinue = props.onDone
  }

  const footer = (
    <StepFlowFooter
      start={<Button variant="outline" onClick={close}>{checkedOut ? t("Close") : t("Cancel")}</Button>}
      error={error}
      busy={busy || !ctx}
      onBack={!flow.isFirst && !(checkedOut && current === "invoice") ? flow.back : undefined}
      onSkip={flow.step?.optional && !checkedOut ? () => {
        setSkipped((s) => ({ ...s, [current]: true }))
        flow.next()
      } : undefined}
      onContinue={onContinue}
      continueLabel={continueLabel}
      continueDisabled={continueDisabled}
    />
  )

  return (
    <Sheet
      wide
      title={r ? t("Check out {name}", { name: r.guest_name }) : t("Check out")}
      description={r ? [
        r.room_number ? t("Room {n}", { n: r.room_number }) : null,
        r.room_type_name,
        `${r.check_in_date} → ${r.check_out_date}`,
      ].filter(Boolean).join(" · ") : undefined}
      onClose={close}
      footer={footer}
    >
      {!ctx && !loadError && (
        <p className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {t("Loading bill…")}
        </p>
      )}
      {loadError && !ctx && <p role="alert" className="text-sm text-rose-700">{loadError}</p>}
      {ctx && r && (
        <div className="space-y-4">
          <StepFlowHeader
            steps={steps}
            current={current}
            onSelect={(k) => {
              if (checkedOut) return
              if (k === "invoice") return
              flow.goTo(k)
            }}
          />

          {ctx.sop.next_tip && !checkedOut && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
              <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              <p>{ctx.sop.next_tip}</p>
            </div>
          )}

          {current === "review" && (
            <div className="space-y-4">
              <Problems items={reviewProblems} folioLink={folioLink} />
              {ctx.notices.length > 0 && (
                <ul className="space-y-1 rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
                  {ctx.notices.map((n) => <li key={n.code}>{n.message}</li>)}
                </ul>
              )}
              <Section title={t("Stay summary")}>
                <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  {[
                    [t("Charges"), ctx.totals.charges, ""],
                    [t("Paid"), ctx.totals.paid, ""],
                    [t("Guest owes"), ctx.totals.owed, "text-rose-700"],
                    [t("Owed to guest"), ctx.totals.refund_due, "text-amber-700"],
                  ].map(([label, n, tone]) => (
                    <div key={String(label)}>
                      <dt className="text-xs text-zinc-500">{label}</dt>
                      <dd className={cn("font-medium tabular-nums", String(tone))}>{fmt(Number(n))}</dd>
                    </div>
                  ))}
                </dl>
                {ctx.totals.to_city_ledger > EPS && (
                  <p className="mt-2 text-xs text-sky-800">
                    {t("{amount} is billed to the company.", { amount: fmt(ctx.totals.to_city_ledger) })}
                  </p>
                )}
              </Section>

              {ctx.pending_bills.length > 0 && (
                <Section title={t("Bills not on the folio yet")} tone="warn">
                  <ul className="space-y-3 text-sm">
                    {ctx.pending_bills.map((b) => (
                      <li key={b.name} className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <span>
                          <span className="font-medium">{b.label}</span>{" "}
                          <span className="text-zinc-500">· {b.name} · {t(b.status)}</span>
                          {b.complimentary ? (
                            <span className="ms-1 text-xs text-zinc-500">({t("complimentary")})</span>
                          ) : null}
                          <span className="ms-2 font-medium tabular-nums">{fmt(b.amount)}</span>
                        </span>
                        <span className="flex flex-wrap items-center gap-2">
                          {b.can_post_to_room ? (
                            <Button variant="outline" disabled={busy} onClick={() => void postToRoom(b)}>
                              {t("Post to room")}
                            </Button>
                          ) : (
                            <span className="text-xs text-zinc-500">{t("Not ready to deliver yet")}</span>
                          )}
                          {b.pay_modes.length > 0 && (
                            <>
                              <select
                                aria-label={t("Payment mode")}
                                className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                                value={outletModes[b.name] || b.pay_modes[0]}
                                onChange={(e) => setOutletModes((m) => ({ ...m, [b.name]: e.target.value }))}
                              >
                                {b.pay_modes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
                              </select>
                              <Button variant="ghost" disabled={busy} onClick={() => void payAtOutlet(b)}>
                                {t("Settle separately")}
                              </Button>
                            </>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {GROUP_ORDER.filter((g) => ctx.groups[g]).map((g) => {
                const grp = ctx.groups[g]
                return (
                  <Section key={g} title={`${t(g)} · ${fmt(grp.amount)}`}>
                    <ul className="divide-y divide-zinc-100 text-sm">
                      {grp.lines.map((line) => (
                        <li key={line.name} className="flex items-start justify-between gap-3 py-1.5">
                          <span className="min-w-0 text-zinc-700">
                            <span className="font-medium">{t(line.charge_type)}</span>
                            {line.description ? <span className="text-zinc-500">: {line.description}</span> : null}
                            {line.is_alcohol ? (
                              <span className="ms-1 text-[10px] font-semibold uppercase text-rose-600">{t("Guest only")}</span>
                            ) : null}
                            <span className="ms-1 text-xs text-zinc-400">({t(line.folio_type)})</span>
                          </span>
                          <span className="shrink-0 tabular-nums text-zinc-800">
                            {fmt(line.amount + line.gst_amount)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Section>
                )
              })}

              <ul className="space-y-1 text-xs text-zinc-500">
                {ctx.folios.map((f) => (
                  <li key={f.folio} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      {t("{type} folio", { type: t(f.folio_type) })} · {f.folio}
                      {f.invoice_number ? ` · ${f.invoice_number}` : ""} · {t("Balance")} {fmt(f.balance)}
                    </span>
                    <a href={folioLink(f.folio)} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                      {t("Open folio")}
                      <ExternalLink className="size-3" aria-hidden />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {current === "late" && ctx.late_checkout && (
            <div className="space-y-4">
              <Section title={t("Late check-out")} tone="warn">
                <p className="text-sm text-zinc-700">
                  {t("Check-out time is {time}; it is now {now}.", {
                    time: ctx.late_checkout.checkout_time, now: ctx.late_checkout.now,
                  })}{" "}
                  {ctx.late_checkout.already_charged
                    ? t("A late check-out charge is already on the bill.")
                    : t("Add the late check-out fee your property charges, or skip to waive it.")}
                </p>
                {!ctx.late_checkout.already_charged && (ctx.late_checkout.folio ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Amount")}</span>
                      <input className={inputCls} type="number" min="0" inputMode="decimal"
                        value={lateAmt} onChange={(e) => setLateAmt(e.target.value)} />
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Tax rate")}</span>
                      <select className={inputCls} value={lateRate} onChange={(e) => setLateRate(e.target.value)}>
                        {Array.from(new Set([...(loc.tax_rates ?? []), ctx.late_checkout.tax_rate])).map((n) => (
                          <option key={n} value={String(n)}>{n}%</option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Description")}</span>
                      <input className={inputCls} value={lateDesc} onChange={(e) => setLateDesc(e.target.value)} />
                    </label>
                    <div className="sm:col-span-3">
                      <Button disabled={busy || !(Number(lateAmt) > 0)} onClick={() => void addLateFee()}>
                        {t("Add late check-out fee")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-rose-700">
                    {t("The guest folio is closed, so a charge can't be added here. Open the folio.")}
                  </p>
                ))}
              </Section>
            </div>
          )}

          {current === "company" && (
            <div className="space-y-4">
              <Problems items={blockersFor("company")} />
              <Section title={t("What the company pays")} tone="info">
                {ctx.city_ledger.length ? (
                  <ul className="space-y-1 text-sm text-sky-900">
                    {ctx.city_ledger.map((c) => (
                      <li key={c.folio} className="flex flex-wrap justify-between gap-2">
                        <span>{t("{type} folio", { type: t("Company") })} · {c.folio} → {c.company_name}</span>
                        <span className="font-medium tabular-nums">{fmt(c.amount)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-zinc-600">{t("Nothing moves to the company's account.")}</p>
                )}
                {ctx.billing.rules.length > 0 && (
                  <ul className="mt-2 space-y-0.5 text-xs text-zinc-600">
                    {ctx.billing.rules.map((rule) => (
                      <li key={rule.charge_type}>{t(rule.charge_type)}: {t(rule.pay_by)}</li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-xs text-zinc-500">
                  {t("At check-out this moves to the company's account (city ledger). Alcohol always stays with the guest.")}
                </p>
              </Section>
              {credit && !credit.ok && (
                <Section title={creditBlocked ? t("Company credit is blocked") : t("Company credit warning")} tone="warn">
                  <ul className="list-disc space-y-1 ps-5 text-sm text-zinc-700">
                    {credit.checks.filter((c) => !c.ok).flatMap((c) =>
                      c.reasons.map((reason) => <li key={c.company + reason}>{reason}</li>))}
                  </ul>
                  {creditBlocked && credit.can_override && (
                    <label className="mt-3 block">
                      <span className="mb-1 block text-sm text-zinc-600">
                        {t("Reason for the override (logged with your name)")}
                      </span>
                      <textarea className={inputCls} rows={3} maxLength={500} value={override}
                        onChange={(e) => setOverride(e.target.value)} />
                    </label>
                  )}
                  {creditBlocked && !credit.can_override && (
                    <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
                      {t("Ask Finance or a Hotel Admin to override it, take payment from the guest, or have the company settle its account first.")}
                    </p>
                  )}
                </Section>
              )}
              <label className="flex items-start gap-2 text-sm text-zinc-800">
                <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" checked={companyOk}
                  onChange={(e) => setCompanyOk(e.target.checked)} />
                {t("I confirmed with the guest that the company pays this part of the bill.")}
              </label>
            </div>
          )}

          {current === "settle" && (
            <div className="space-y-4">
              <Problems items={settleProblems} folioLink={folioLink} />
              {settleDone && (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                  <Check className="me-1 inline size-4" aria-hidden />
                  {t("The guest's bill is settled.")}
                </p>
              )}

              {ctx.collect.length > 0 && (
                <Section title={t("The guest owes {amount}", { amount: fmt(collectTotal) })}>
                  <ul className="mb-3 space-y-1 text-sm text-zinc-700">
                    {ctx.collect.map((c) => (
                      <li key={c.folio} className="flex justify-between gap-2">
                        <span>{t("{type} folio", { type: t(c.folio_type) })} · {c.folio}</span>
                        <span className="font-medium tabular-nums">{fmt(c.amount)}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Payment mode")}</span>
                      <select className={inputCls} value={payMode} onChange={(e) => setPayMode(e.target.value)}>
                        {ctx.payment_modes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
                      </select>
                    </label>
                    <label className="block text-xs">
                      <span className="mb-1 block text-zinc-500">{t("Reference (optional)")}</span>
                      <input className={inputCls} value={payRef} onChange={(e) => setPayRef(e.target.value)} />
                    </label>
                  </div>
                  <Button className="mt-3 w-full sm:w-auto" disabled={busy || !ctx.till_open} onClick={() => void collect()}>
                    {t("Collect {amount}", { amount: fmt(collectTotal) })}
                  </Button>
                </Section>
              )}

              {ctx.refunds.length > 0 && (
                <Section title={t("The guest is owed {amount}", { amount: fmt(refundTotal) })}>
                  <ul className="mb-3 space-y-2 text-sm text-zinc-700">
                    {ctx.refunds.map((rf) => (
                      <li key={rf.kind + rf.folio} className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <span>
                          {rf.source === "security_deposit"
                            ? t("Security deposit held")
                            : t("Paid more than the bill")}
                          <span className="ms-2 font-medium tabular-nums">{fmt(rf.amount)}</span>
                        </span>
                        <select
                          aria-label={t("Refund by")}
                          className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm"
                          value={refundModes[rf.kind + rf.folio] || rf.mode}
                          onChange={(e) => setRefundModes((m) => ({ ...m, [rf.kind + rf.folio]: e.target.value }))}
                        >
                          {ctx.payment_modes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
                        </select>
                      </li>
                    ))}
                  </ul>
                  <label className="block text-xs">
                    <span className="mb-1 block text-zinc-500">{t("Reason (required, goes on the record)")}</span>
                    <input className={inputCls} value={refundReason} onChange={(e) => setRefundReason(e.target.value)} />
                  </label>
                  <Button className="mt-3 w-full sm:w-auto" disabled={busy || !ctx.till_open || !refundReason.trim()}
                    onClick={() => void refund()}>
                    {t("Refund {amount}", { amount: fmt(refundTotal) })}
                  </Button>
                </Section>
              )}

              {ctx.deposit && ctx.deposit.held > EPS && ctx.actions.can_withhold_deposit && (
                <Section title={t("Damage to the room?")}>
                  <p className="mb-2 text-xs text-zinc-500">
                    {t("Keep part of the security deposit ({held} held) against damage before refunding the rest.", {
                      held: fmt(ctx.deposit.held),
                    })}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <input className={inputCls} type="number" min="0" inputMode="decimal"
                      placeholder={t("Amount")} value={withholdAmt}
                      onChange={(e) => setWithholdAmt(e.target.value)} />
                    <input className={cn(inputCls, "sm:col-span-2")} placeholder={t("What was damaged")}
                      value={withholdReason} onChange={(e) => setWithholdReason(e.target.value)} />
                  </div>
                  <Button className="mt-2" variant="outline"
                    disabled={busy || !(Number(withholdAmt) > 0) || !withholdReason.trim()}
                    onClick={() => void withhold()}>
                    {t("Withhold for damage")}
                  </Button>
                </Section>
              )}

              <p className="text-xs text-zinc-500">
                {t("Anything unusual (a split, an allowance, a correction)? Open the folio, then come back here.")}{" "}
                {ctx.folios[0] && (
                  <a href={folioLink(ctx.folios[0].folio)} target="_blank" rel="noreferrer"
                    className="font-medium text-brand-700 hover:underline">
                    {t("Open folio")}
                  </a>
                )}
              </p>
            </div>
          )}

          {current === "guest" && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-600">
                {t("Your property's check-out routine. Tick each one as you go.")}
              </p>
              {guestSteps.map((s) => {
                const done = ticked[s.step_key] || s.state === "done"
                return (
                  <button key={s.step_key || s.title} type="button"
                    onClick={() => setTicked((p) => ({ ...p, [s.step_key]: !p[s.step_key] }))}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-xl border p-3 text-start",
                      done ? "border-emerald-200 bg-emerald-50/60" : "border-zinc-200 hover:border-brand-300",
                    )}>
                    <span className={cn(
                      "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
                      done ? "border-emerald-500 bg-emerald-500 text-white" : "border-zinc-300",
                    )}>
                      {done ? <Check className="size-3" aria-hidden /> : null}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-zinc-800">{t(s.title)}</span>
                      <span className="mt-1 block text-sm text-zinc-600">
                        {s.prompt_to_guest ? `"${t(s.prompt_to_guest)}"` : s.tip || t(s.instruction)}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {current === "confirm" && (
            <div className="space-y-4">
              <Problems items={ctx.blockers.filter((b) => !["owed", "refund", "credit_blocked"].includes(b.code))}
                folioLink={folioLink} />
              <Section title={t("Ready to check out")}>
                <ul className="space-y-1 text-sm text-zinc-700">
                  <li>
                    {r.guest_name}
                    {r.room_number ? ` · ${t("Room {n}", { n: r.room_number })}` : ""}
                  </li>
                  <li>{t("Guest's balance")}: {fmt(ctx.totals.owed - ctx.totals.refund_due)}</li>
                  {ctx.totals.to_city_ledger > EPS && (
                    <li className="text-sky-800">
                      {t("{amount} moves to the company's account.", { amount: fmt(ctx.totals.to_city_ledger) })}
                    </li>
                  )}
                </ul>
              </Section>
              {!ctx.settled && (
                <p className="text-sm text-rose-700">{t("Settle the guest's bill first (Payment step).")}</p>
              )}
              {ctx.companions.length > 0 && (
                <Section title={t("Others from this group still in house")} tone="warn">
                  <p className="mb-2 text-xs text-amber-800">
                    {t("This checks out {name} only. Check out the others one at a time when they leave.", { name: r.guest_name })}
                  </p>
                  <ul className="space-y-1.5 text-sm">
                    {ctx.companions.map((c) => (
                      <li key={c.name} className="flex items-center justify-between gap-2">
                        <span>
                          {c.guest_name}
                          {c.room_number ? ` · ${t("Room {n}", { n: c.room_number })}` : ""}
                        </span>
                        {props.onOpenReservation && (
                          <button type="button" className="text-sm font-medium text-brand-700 hover:underline"
                            onClick={() => props.onOpenReservation?.(c.name)}>
                            {t("Check out")}
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
              <p className="text-xs text-zinc-500">
                {t("Checking out frees the room for housekeeping and records who checked the guest out.")}
              </p>
            </div>
          )}

          {current === "invoice" && (
            <div className="space-y-4">
              {checkedOut ? (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                  <Check className="me-1 inline size-4" aria-hidden />
                  {t("{name} is checked out.", { name: r.guest_name })}
                </p>
              ) : (
                <p className="text-sm text-zinc-600">{t("Invoices are issued once the guest is checked out.")}</p>
              )}
              {creditWarnings.length > 0 && (
                <Section title={t("Checked out with a company credit warning")} tone="warn">
                  <ul className="list-disc ps-5 text-sm">{creditWarnings.map((w) => <li key={w}>{w}</li>)}</ul>
                </Section>
              )}
              {checkedOut && (() => {
                const own = ctx.folios.filter((f) => f.side !== "group")
                const ready = own.filter((f) => f.status === "Open" && f.has_charges && Math.abs(f.balance) <= EPS)
                return (
                  <Section title={t("Invoices")}>
                    <ul className="divide-y divide-zinc-100 text-sm">
                      {own.map((f) => (
                        <li key={f.folio} className="flex flex-col gap-2 py-2 sm:flex-row sm:items-center sm:justify-between">
                          <span>
                            {t("{type} folio", { type: t(f.folio_type) })} · {f.folio}
                            {f.invoice_number ? (
                              <span className="ms-2 font-medium text-emerald-700">{f.invoice_number}</span>
                            ) : null}
                          </span>
                          {f.status === "Closed" ? (
                            <a href={folioLink(f.folio)} target="_blank" rel="noreferrer"
                              className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
                              <Printer className="size-4" aria-hidden />
                              {t("View or print")}
                            </a>
                          ) : !f.has_charges ? (
                            <span className="text-xs text-zinc-500">{t("Nothing to invoice")}</span>
                          ) : Math.abs(f.balance) > EPS ? (
                            <a href={folioLink(f.folio)} target="_blank" rel="noreferrer"
                              className="text-xs font-medium text-rose-700 underline">
                              {t("Has a balance of {amount}: open the folio", { amount: fmt(f.balance) })}
                            </a>
                          ) : (
                            <Button variant="outline" disabled={busy} onClick={() => void invoice([f.folio])}>
                              {t("Close and generate invoice")}
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                    {ready.length > 1 && (
                      <Button className="mt-3" disabled={busy} onClick={() => void invoice(ready.map((f) => f.folio))}>
                        {t("Generate all invoices")}
                      </Button>
                    )}
                  </Section>
                )
              })()}
            </div>
          )}
        </div>
      )}
    </Sheet>
  )
}
