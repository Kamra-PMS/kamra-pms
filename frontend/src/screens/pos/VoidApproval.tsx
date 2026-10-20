/*  Cancel a bill, or void a line, with the rule the server enforces:
    nothing sent to the kitchen = a reason is enough; food the kitchen
    already has = a void reason and a supervisor's approval (their own
    session, or their user and PIN typed on this till). The kitchen keeps
    seeing what was voided until it acknowledges; nothing is deleted. */

import { useEffect, useState } from "react"
import { AlertTriangle, ShieldCheck } from "lucide-react"
import { call } from "../../lib/api"
import { useT } from "../../lib/i18n"
import { Button } from "../../components/ui/button"

export interface VoidArgs {
  reason: string
  reason_code: string | null
  supervisor: string | null
  supervisor_pin: string | null
}

interface ReasonCode { name: string; code: string; description: string }
interface Approver { user: string; full_name: string }

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function VoidApproval({
  outlet, title, kitchenCount, canApprove, busy, confirmLabel, onConfirm, onClose,
}: {
  outlet: string
  title: string
  /** live lines the kitchen already has (0 = a reason is enough) */
  kitchenCount: number
  /** the signed-in user is a supervisor and approves for themselves */
  canApprove: boolean
  busy: boolean
  confirmLabel: string
  onConfirm: (a: VoidArgs) => void
  onClose: () => void
}) {
  const { t } = useT()
  const needsApproval = kitchenCount > 0
  const [reason, setReason] = useState("")
  const [code, setCode] = useState("")
  const [codes, setCodes] = useState<ReasonCode[]>([])
  const [approvers, setApprovers] = useState<Approver[] | null>(null)
  const [sup, setSup] = useState("")
  const [pin, setPin] = useState("")

  useEffect(() => {
    if (!needsApproval) return
    call<ReasonCode[]>("kamra.ledger.list_reason_codes", { category: "Void" })
      // a failed reload keeps what an earlier one returned; free text still works
      .then(setCodes).catch(() => {})
    if (!canApprove) {
      call<Approver[]>("kamra.pos.void_approvers", { outlet })
        .then((a) => { setApprovers(a); if (a.length === 1) setSup(a[0].user) })
        .catch(() => setApprovers((a) => a ?? []))
    }
  }, [needsApproval, canApprove, outlet])

  const ready = (reason.trim() || code) &&
    (!needsApproval || canApprove || (sup && pin.trim()))
  const submit = () => {
    if (!ready || busy) return
    onConfirm({
      reason: reason.trim(), reason_code: code || null,
      supervisor: needsApproval && !canApprove ? sup : null,
      supervisor_pin: needsApproval && !canApprove ? pin.trim() : null,
    })
  }

  return (
    <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50 p-2.5">
      <p className="text-xs font-semibold text-rose-800">{title}</p>
      {needsApproval ? (
        <p className="flex gap-1.5 text-xs text-rose-800">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            {t("The kitchen already has {n} item(s). They are voided, not deleted: the kitchen is told to stop, and a supervisor approves.", { n: kitchenCount })}
          </span>
        </p>
      ) : (
        <p className="text-xs text-rose-700">{t("Nothing was sent to the kitchen. A reason is enough.")}</p>
      )}
      {needsApproval && codes.length > 0 && (
        <select className={inputCls} value={code} onChange={(e) => setCode(e.target.value)}
          aria-label={t("Void reason")}>
          <option value="">{t("Reason…")}</option>
          {codes.map((c) => <option key={c.name} value={c.name}>{c.description}</option>)}
        </select>
      )}
      <input autoFocus className={inputCls} value={reason}
        placeholder={needsApproval ? t("Details (optional with a reason above)") : t("Reason, e.g. guest left")}
        onChange={(e) => setReason(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()} />
      {needsApproval && (canApprove ? (
        <p className="flex items-center gap-1.5 text-xs text-emerald-800">
          <ShieldCheck className="size-3.5" aria-hidden />{t("You approve this as a supervisor.")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_7rem]">
          <select className={inputCls} value={sup} onChange={(e) => setSup(e.target.value)}
            aria-label={t("Supervisor")}>
            <option value="">{approvers === null ? t("Loading…") : t("Supervisor…")}</option>
            {(approvers || []).map((a) => <option key={a.user} value={a.user}>{a.full_name}</option>)}
          </select>
          <input className={inputCls} type="password" inputMode="numeric" autoComplete="off"
            value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
            placeholder={t("Their PIN")} aria-label={t("Supervisor PIN")}
            onKeyDown={(e) => e.key === "Enter" && submit()} />
          {approvers !== null && approvers.length === 0 && (
            <p className="text-xs text-rose-700 sm:col-span-2">
              {t("No supervisor with a cashier PIN can approve here yet. A Hotel Admin or Finance user sets a PIN first.")}
            </p>
          )}
        </div>
      ))}
      <div className="flex gap-1.5">
        <Button variant="outline" className="h-10 flex-1 font-semibold text-rose-700"
          disabled={busy || !ready} onClick={submit}>
          {confirmLabel}
        </Button>
        <Button variant="ghost" className="h-10" onClick={onClose}>{t("Back")}</Button>
      </div>
    </div>
  )
}
