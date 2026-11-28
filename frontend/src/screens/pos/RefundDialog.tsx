/*  Giving money back on a paid bill: the whole of what is left, chosen items
    or an amount, with a reason and an approval (see refundApproval). The figures come from
    kamra.pos_refunds (refund_options, refund_quote), so the screen never
    works money out itself; refund_bill pays an attempt's key only once. */

import { useEffect, useState } from "react"
import { ShieldCheck, X } from "lucide-react"
import { call } from "../../lib/api"
import { serverError } from "../../lib/resource"
import { cur, fmtAmount } from "../../lib/money"
import { useT, t as translate } from "../../lib/i18n"
import { cn } from "../../lib/utils"
import { Button } from "../../components/ui/button"
import { newAttemptKey, refundApproval, refundClick, refundRequest, type RefundKind } from "../../lib/refunds"
import { useCashierAuth } from "../../lib/cashierAuth"
import CashierPinDialog from "../../components/CashierPinDialog"

interface Options {
  eligible: boolean
  why_not: string | null
  paid: number
  refunded: number
  remaining: number
  lines: { row: string; item_name: string; choices: string[]; qty: number; refunded_qty: number; can_restock: boolean }[]
  modes: string[]
  reasons: { code: string; label: string }[]
  approvers: { user: string; full_name: string }[]
  can_approve: boolean
  pin_required: boolean
  has_pin: boolean
}
interface Quote { amount: number; lines: { row: string; qty: number; amount: number }[] }

const box = "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm"

export default function RefundDialog({ order, onClose, onDone }: {
  order: string; onClose: () => void; onDone: () => void
}) {
  const { t } = useT()
  const { refresh: refreshPinStatus } = useCashierAuth()
  const [settingPin, setSettingPin] = useState(false)
  const [opts, setOpts] = useState<Options | null>(null)
  const [kind, setKind] = useState<RefundKind>("whole")
  const [qtys, setQtys] = useState<Record<string, string>>({})
  const [back, setBack] = useState<Record<string, boolean>>({})
  const [amount, setAmount] = useState("")
  const [reason, setReason] = useState("")
  const [note, setNote] = useState("")
  const [mode, setMode] = useState("")
  const [supervisor, setSupervisor] = useState("")
  const [pin, setPin] = useState("")
  const [quote, setQuote] = useState<{ ask: string; got: Quote } | null>(null)
  const [error, setError] = useState<string | null>(null)
  // why the last attempt was refused: it stays while the new figures load
  const [refused, setRefused] = useState<{ ask: string; why: string } | null>(null)
  const [round, setRound] = useState(0)
  const [busy, setBusy] = useState(false)
  // the confirmation a one-tap refund waits for
  const [asked, setAsked] = useState<{ what: string; at: number } | null>(null)
  // one key for this attempt: a retried click can't pay twice
  const [key] = useState(newAttemptKey)

  useEffect(() => {
    call<Options>("kamra.pos_refunds.refund_options", { order }).then((o) => {
      setOpts(o)
      setMode((m) => m || (o.modes[0] ?? ""))
      setReason((r) => r || (o.reasons[0]?.code ?? ""))
      setSupervisor((s) => s || (o.approvers[0]?.user ?? ""))
    }).catch((e) => setError(serverError(e)))
  }, [order, round])

  const request = refundRequest(kind, qtys, back, amount)
  const ask = request ? JSON.stringify(request) : ""
  useEffect(() => {
    if (!ask) return
    let live = true
    const wait = setTimeout(() => {
      call<Quote>("kamra.pos_refunds.refund_quote", { order, ...JSON.parse(ask) })
        .then((got) => { if (live) { setQuote({ ask, got }); setError(null) } })
        .catch((e) => { if (live) { setQuote(null); setError(serverError(e)) } })
    }, 250)
    return () => { live = false; clearTimeout(wait) }
  }, [ask, order, round])
  const current = quote && quote.ask === ask ? quote.got : null
  const money = (n: number) => `${cur()}${fmtAmount(n)}`
  const needsNote = reason === "POS-REF-OTHER" && !note.trim()
  const problem = (refused?.ask === ask ? refused.why : null) ?? error
  const approval = opts ? refundApproval(opts, supervisor, pin) : null
  const ready = !!current && !!reason && !needsNote && !!mode && !!approval?.ready

  const what = JSON.stringify([ask, mode, reason, current?.amount])
  const confirming = approval?.ask === "nothing" && asked?.what === what
  // a change drops the question: changing back must not bring it up unasked
  useEffect(() => { setAsked(null) }, [what])
  function takeBack() {
    // the second tap of a double tap can land here: it must not undo the question
    if (asked && refundClick("nothing", asked, what, Date.now()) === "ignore") return
    setAsked(null)
  }
  function press() {
    if (!approval) return
    const at = Date.now()
    const step = refundClick(approval.ask, asked, what, at)
    if (step === "ask") setAsked({ what, at })
    else if (step === "pay") void give()
  }

  async function give() {
    if (!request) return
    if (!current || !approval) return
    setBusy(true); setError(null); setRefused(null)
    try {
      await call("kamra.pos_refunds.refund_bill", {
        order, ...request, mode, reason_code: reason, note: note.trim() || null,
        ...approval.args, idempotency_key: key, expected_amount: current.amount,
        // after a lost answer this tells "send it again" from "refund more"
        seen_refunded: opts?.refunded,
      })
      onDone()
    } catch (e) {
      // the bill may have moved on: read it and the figure again
      setRefused({ ask, why: serverError(e) }); setPin(""); setBusy(false); setAsked(null)
      setQuote(null); setRound((n) => n + 1)
    }
  }

  const shareOf = (row: string) => current?.lines.find((l) => l.row === row)?.amount
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-zinc-900/40 p-3">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <h2 className="text-lg font-bold text-zinc-800">{t("Refund bill {bill}", { bill: order })}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")}
            className="grid size-9 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-5 text-sm">
          {!opts ? (!error && <p className="text-zinc-400">{t("Loading…")}</p>) : !opts.eligible ? (
            <p className="text-zinc-700">{translate(opts.why_not ?? "")}</p>
          ) : (
            <>
              <p className="text-zinc-600">
                {t("Paid {paid} · already refunded {refunded}", { paid: money(opts.paid), refunded: money(opts.refunded) })}
              </p>
              <div className="flex flex-wrap gap-4">
                {(["whole", "items", "amount"] as const).map((k) => (
                  <label key={k} className="flex items-center gap-1.5">
                    <input type="radio" checked={kind === k} onChange={() => { setKind(k); setError(null) }} />
                    {k === "whole" ? t("Whole bill") : k === "items" ? t("Chosen items") : t("An amount")}
                  </label>
                ))}
              </div>
              {kind === "amount" ? (
                <input className={cn(box, "w-48")} type="number" min="0" step="any" inputMode="decimal"
                  value={amount} onChange={(e) => setAmount(e.target.value)}
                  placeholder={t("Up to {amount}", { amount: money(opts.remaining) })} aria-label={t("An amount")} />
              ) : (
                <table className="w-full">
                  <thead className="text-left text-xs uppercase text-zinc-400">
                    <tr>
                      <th className="pb-1">{t("Item")}</th><th className="pb-1 pr-3 text-right">{t("Left")}</th>
                      {kind === "items" && <th className="pb-1">{t("Refund")}</th>}
                      <th className="pb-1 pr-3 text-right">{t("Amount")}</th><th className="pb-1">{t("Back to stock")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {opts.lines.map((l) => {
                      const left = Math.round((l.qty - l.refunded_qty) * 1000) / 1000
                      const share = shareOf(l.row)
                      const label = [l.item_name, ...l.choices].join(", ")
                      return (
                        <tr key={l.row} className={cn(left <= 0 && "text-zinc-400")}>
                          <td className="py-1.5">
                            {l.item_name}
                            {l.choices.length > 0 && <span className="block text-xs text-zinc-500">{l.choices.join(", ")}</span>}
                          </td>
                          <td className="py-1.5 pr-3 text-right tabular-nums">{left}</td>
                          {kind === "items" && (
                            <td className="py-1.5">
                              <input className={cn(box, "w-20")} type="number" min="0" max={left} step="any" disabled={left <= 0}
                                value={qtys[l.row] ?? ""} onChange={(e) => setQtys({ ...qtys, [l.row]: e.target.value })}
                                aria-label={`${label} · ${t("Refund")}`} />
                            </td>
                          )}
                          <td className="py-1.5 pr-3 text-right tabular-nums">{share === undefined ? "-" : money(share)}</td>
                          <td className="py-1.5">
                            {l.can_restock && left > 0 && (
                              <input type="checkbox" checked={!!back[l.row]} aria-label={`${label} · ${t("Back to stock")}`}
                                onChange={(e) => setBack({ ...back, [l.row]: e.target.checked })} />
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1">
                  <span className="font-medium text-zinc-600">{t("Reason")}</span>
                  <select className={box} value={reason} onChange={(e) => setReason(e.target.value)}>
                    {opts.reasons.map((r) => <option key={r.code} value={r.code}>{translate(r.label)}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-medium text-zinc-600">{needsNote ? t("Note (required)") : t("Note")}</span>
                  <input className={box} value={note} onChange={(e) => setNote(e.target.value)} />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-medium text-zinc-600">{t("Money back as")}</span>
                  <select className={box} value={mode} onChange={(e) => setMode(e.target.value)}>
                    {opts.modes.map((m) => <option key={m} value={m}>{translate(m)}</option>)}
                  </select>
                </label>
                <div />
                {approval?.ask === "supervisor" && (
                  <>
                    <label className="flex flex-col gap-1">
                      <span className="font-medium text-zinc-600">{t("Supervisor")}</span>
                      <select className={box} value={supervisor} onChange={(e) => { setSupervisor(e.target.value); setPin("") }}>
                        {opts.approvers.map((a) => <option key={a.user} value={a.user}>{a.full_name}</option>)}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="font-medium text-zinc-600">{t("Supervisor's PIN")}</span>
                      <input className={box} type="password" inputMode="numeric" autoComplete="one-time-code"
                        value={pin} onChange={(e) => setPin(e.target.value)} />
                    </label>
                  </>
                )}
                {approval?.ask === "own-pin" && (
                  <label className="flex flex-col gap-1">
                    <span className="font-medium text-zinc-600">{t("Your cashier PIN")}</span>
                    <input className={box} type="password" inputMode="numeric" autoComplete="one-time-code"
                      value={pin} onChange={(e) => setPin(e.target.value)} />
                  </label>
                )}
              </div>
              {approval?.ask === "nothing" && (
                <p className="flex items-center gap-1.5 text-emerald-800">
                  <ShieldCheck className="size-4" aria-hidden />{t("You approve this as a supervisor.")}
                </p>
              )}
              {approval?.ask === "set-pin" && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
                  <span>{t("Set your cashier PIN to approve this refund.")}</span>
                  <Button variant="outline" className="h-9" onClick={() => setSettingPin(true)}>
                    {t("Set my cashier PIN")}
                  </Button>
                </div>
              )}
              {approval?.ask === "supervisor" && opts.approvers.length === 0 && (
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
                  {t("No supervisor has a cashier PIN yet. A supervisor sets one from the account menu: Set my cashier PIN.")}
                </p>
              )}
            </>
          )}
          {problem && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-rose-700">{translate(problem)}</div>}
        </div>
        {opts?.eligible && (confirming && current ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-amber-200 bg-amber-50 p-4">
            <span role="alert" className="text-sm font-semibold text-amber-900">
              {t("Give back {amount} by {mode}?", { amount: money(current.amount), mode: translate(mode) })}
            </span>
            <div className="ml-auto flex gap-2">
              <Button className="h-11 px-6" disabled={busy || !ready} onClick={press}>
                {t("Yes, refund {amount}", { amount: money(current.amount) })}
              </Button>
              <Button variant="outline" className="h-11 px-6" disabled={busy} onClick={takeBack}>
                {t("Back")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3 border-t border-zinc-200 p-4">
            <span className="text-sm text-zinc-600">
              {t("Total back")} <b className="tabular-nums text-zinc-900">{current ? money(current.amount) : "-"}</b>
            </span>
            <Button className="h-11 px-6" disabled={busy || !ready} onClick={press}>
              {current ? t("Refund {amount}", { amount: money(current.amount) }) : t("Refund")}
            </Button>
          </div>
        ))}
      </div>
      {settingPin && (
        <CashierPinDialog onClose={() => setSettingPin(false)}
          onSaved={() => { setSettingPin(false); setRound((n) => n + 1); void refreshPinStatus() }} />
      )}
    </div>
  )
}
