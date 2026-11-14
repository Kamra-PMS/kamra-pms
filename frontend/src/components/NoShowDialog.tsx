/*  Mark an arrival a no-show from Today, the reservation or End of Day
    (eod_mark_no_show). The confirm shows what the policy posts first (the
    same numbers no_show_preview computes from the posting code), then, if
    the guest paid more than the fee, offers to refund the rest or keep it
    as a forfeited deposit (settle_no_show_credit). "Decide later" leaves
    it on the audit pack's list for the morning. */

import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { call } from "../lib/api"
import { useCashierAuth } from "../lib/cashierAuth"
import { fmtMoney, useLocale } from "../lib/money"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

interface Preview {
  guest_name: string
  fee: "none" | "waived" | "charge"
  fee_reason: string
  fee_basis: string
  fee_amount: number
  fee_total: number
  paid: number
  credit_after: number
  credit_default: CreditAction
}

type CreditAction = "Refund" | "Keep as forfeited deposit"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function NoShowDialog(props: {
  reservation: string
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const { withPin } = useCashierAuth()
  const { payment_modes } = useLocale()
  const [pre, setPre] = useState<Preview | null>(null)
  const [reason, setReason] = useState("")
  const [credit, setCredit] = useState(0)
  const [action, setAction] = useState<CreditAction>("Refund")
  const [creditReason, setCreditReason] = useState("")
  const [mode, setMode] = useState("Cash")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<Preview>("kamra.night_audit.no_show_preview", { reservation: props.reservation })
      .then((p) => {
        setPre(p)
        setAction(p.credit_default)
      })
      .catch((e) => setError(serverError(e)))
  }, [props.reservation])

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const mark = () =>
    run(async () => {
      const out = await call<{ credit: number }>("kamra.night_audit.eod_mark_no_show", {
        reservation: props.reservation,
        reason: reason.trim() || undefined,
      })
      if (out.credit > 0) setCredit(out.credit)
      else props.onDone()
    })

  const settle = () =>
    run(async () => {
      await withPin((pin) =>
        call("kamra.night_audit.settle_no_show_credit", {
          reservation: props.reservation,
          action,
          reason: creditReason.trim(),
          mode: action === "Refund" ? mode : undefined,
          pin,
        }),
      )
      props.onDone()
    })

  const feeLine = !pre
    ? ""
    : pre.fee === "charge"
      ? t("No-show fee ({basis}): {amount} with tax, posted to the folio.", {
          basis: t(pre.fee_basis), amount: fmtMoney(pre.fee_total),
        })
      : pre.fee === "waived"
        ? t("No fee: waived for this booking ({why}).", { why: pre.fee_reason })
        : t("No fee: the property's no-show policy charges nothing.")

  const close = credit > 0 ? props.onDone : props.onClose

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={t("Mark no-show")}>
      <div className="absolute inset-0 bg-black/40" onClick={close} aria-hidden />
      <div className="relative w-full max-w-md rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">
              {credit > 0 ? t("Guest is in credit") : t("Mark no-show")}
            </h2>
            {pre && <p className="text-sm text-zinc-500">{pre.guest_name}</p>}
          </div>
          <Button variant="ghost" onClick={close} aria-label={t("Close")}>
            <X className="size-5" />
          </Button>
        </header>
        <div className="space-y-3 px-5 py-4 text-sm">
          {credit > 0 ? (
            <>
              <p className="text-zinc-700">
                {t("{amount} paid beyond the no-show fee is still on the folio.", { amount: fmtMoney(credit) })}
              </p>
              <div role="radiogroup" aria-label={t("What to do with it")} className="space-y-1.5">
                {(["Refund", "Keep as forfeited deposit"] as const).map((a) => (
                  <label key={a} className="flex items-center gap-2">
                    <input type="radio" className="size-4 accent-brand-600" checked={action === a}
                      onChange={() => setAction(a)} />
                    {a === "Refund" ? t("Refund it to the guest") : t("Keep it as a forfeited deposit")}
                  </label>
                ))}
              </div>
              {action === "Refund" && (
                <label className="block">
                  <span className="mb-1 block text-zinc-500">{t("Refund by")}</span>
                  <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}>
                    {(payment_modes.length ? payment_modes : ["Cash"]).map((m) => (
                      <option key={m} value={m}>{t(m)}</option>
                    ))}
                  </select>
                </label>
              )}
              <label className="block">
                <span className="mb-1 block text-zinc-500">{t("Reason (required, goes on the record)")}</span>
                <input className={inputCls} value={creditReason} onChange={(e) => setCreditReason(e.target.value)} />
              </label>
            </>
          ) : pre ? (
            <>
              <p className="text-zinc-700">{feeLine}</p>
              <p className="text-zinc-700">
                {pre.paid > 0
                  ? pre.credit_after > 0
                    ? t("Paid {paid}. The fee comes out of it; {left} stays as credit, to refund or keep next.", {
                        paid: fmtMoney(pre.paid), left: fmtMoney(pre.credit_after),
                      })
                    : t("Paid {paid}. It goes against the fee.", { paid: fmtMoney(pre.paid) })
                  : t("Nothing paid in advance.")}
              </p>
              <p className="text-zinc-500">{t("The room goes back on sale now, here and on the channels.")}</p>
              <input className={inputCls} placeholder={t("Note (optional)")} value={reason}
                onChange={(e) => setReason(e.target.value)} />
            </>
          ) : (
            !error && <p className="text-zinc-500">{t("Loading…")}</p>
          )}
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700">{error}</p>}
        </div>
        <footer className="flex justify-end gap-2 border-t border-zinc-100 px-5 py-3">
          {credit > 0 ? (
            <>
              <Button variant="outline" disabled={busy} onClick={props.onDone}>{t("Decide later")}</Button>
              <Button disabled={busy || !creditReason.trim()} onClick={() => void settle()}>
                {action === "Refund"
                  ? t("Refund {amount}", { amount: fmtMoney(credit) })
                  : t("Keep {amount}", { amount: fmtMoney(credit) })}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" disabled={busy} onClick={props.onClose}>{t("Back")}</Button>
              <Button className="bg-rose-600 hover:bg-rose-700" disabled={busy || !pre} onClick={() => void mark()}>
                {t("Mark no-show")}
              </Button>
            </>
          )}
        </footer>
      </div>
    </div>
  )
}
