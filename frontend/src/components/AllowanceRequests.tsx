/*  Allowances waiting for a manager. A manager approves or rejects
    (a rejection says why); at the desk, a manager can approve on the spot
    by picking their name and typing their own PIN. A signed-in manager
    types their PIN too: it is the signature on the allowance voucher.
    Nothing is on the bill until it is approved. The server (kamra.api.decide_allowance) checks who
    may approve; agents never can. */

import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { cur, moneyLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { Button } from "./ui/button"

interface Req {
  name: string
  serial: string | null
  folio: string
  amount: number
  reason: string
  status: "Pending" | "Approved" | "Rejected"
  requested_by: string
  requested_on: string
  channel: string | null
  decided_by: string | null
  decided_by_name?: string | null
  decided_by_title?: string | null
  decided_on: string | null
  decision_note: string | null
  guest_name: string | null
  room: string | null
  folio_status: string | null
  bill_to_name: string | null
}
interface Approver { user: string; full_name: string }

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
const money = (n: number) =>
  `${cur()}${Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`

export default function AllowanceRequests({ property, folio, status = "Pending", refreshKey, onChanged, showStay }: {
  property: string
  folio?: string
  status?: string
  refreshKey?: number
  onChanged?: () => void
  /** list view: show guest, room and a link to the folio */
  showStay?: boolean
}) {
  const { t } = useT()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const [rows, setRows] = useState<Req[] | null>(null)
  const [canDecide, setCanDecide] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [note, setNote] = useState("")
  const [onSpot, setOnSpot] = useState<string | null>(null)
  const [approvers, setApprovers] = useState<Approver[] | null>(null)
  const [sup, setSup] = useState("")
  const [pin, setPin] = useState("")

  const load = useCallback(() => {
    call<{ requests: Req[]; can_decide: boolean }>("kamra.api.allowance_requests", {
      property, status, folio,
    })
      .then((r) => { setRows(r.requests); setCanDecide(r.can_decide) })
      .catch((e) => setError(serverError(e)))
  }, [property, status, folio])
  useEffect(load, [load, refreshKey])

  async function decide(req: string, params: Record<string, unknown>, ownPin: boolean) {
    setBusy(true)
    setError(null)
    try {
      if (ownPin && pinStatus?.required) await ensureUnlocked()
      await call("kamra.api.decide_allowance", { allowance_request: req, ...params })
      setRejecting(null); setOnSpot(null); setNote(""); setPin("")
      load()
      onChanged?.()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  function startOnSpot(req: string) {
    setOnSpot(req)
    if (approvers === null)
      call<Approver[]>("kamra.api.allowance_approvers", { property })
        .then((a) => { setApprovers(a); if (a.length === 1) setSup(a[0].user) })
        .catch(() => setApprovers([]))
  }

  if (!rows) return error ? <p className="text-sm text-rose-600">{translate(error)}</p> : null
  if (!rows.length)
    return showStay ? <p className="py-6 text-center text-sm text-zinc-400">{t("Nothing here.")}</p> : null

  return (
    <div className="space-y-2">
      {!showStay && (
        <p className="text-xs font-medium uppercase tracking-wider text-amber-700">
          {t("Waiting for a manager's approval")}
        </p>
      )}
      {rows.map((r) => (
        <div key={r.name} className="rounded-lg border border-amber-200 bg-amber-50/60 p-2.5 text-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium tabular-nums">{money(r.amount)}</span>
            <span className="min-w-0 flex-1 text-zinc-700">{r.reason}</span>
            {showStay && (
              <Link to={`/billing/${encodeURIComponent(r.folio)}`} className="text-xs text-brand-700 hover:underline">
                {[r.room, r.bill_to_name || r.guest_name, r.folio].filter(Boolean).join(" · ")}
              </Link>
            )}
          </div>
          <p className="mt-0.5 text-xs text-zinc-500">
            {t("Asked by {who} on {when}", { who: r.requested_by, when: String(r.requested_on).slice(0, 16) })}
            {r.channel && r.channel !== "Desk" ? ` · ${r.channel}` : ""}
          </p>
          {r.status !== "Pending" && (
            <p className="mt-0.5 text-xs text-zinc-600">
              {r.status === "Approved"
                ? (r.decided_by
                    ? t("Approved by {who}", {
                        who: [r.decided_by_name || r.decided_by, r.decided_by_title && translate(r.decided_by_title)]
                          .filter(Boolean).join(", "),
                      })
                    : t("Posted without approval"))
                : t("Rejected by {who}: {why}", { who: r.decided_by ?? "", why: r.decision_note ?? "" })}
              {r.serial && (
                <>
                  {" · "}
                  <span className="font-mono">{r.serial}</span>{" · "}
                  <Link to={`/allowance-voucher/${encodeURIComponent(r.serial)}`}
                    className="text-brand-700 hover:underline">
                    {t("Print voucher")}
                  </Link>
                </>
              )}
            </p>
          )}
          {r.status === "Pending" && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {canDecide ? (
                <>
                  <input className={`${inputCls} w-24`} type="password" inputMode="numeric" autoComplete="off"
                    value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
                    placeholder={t("Your PIN")} aria-label={t("Your PIN")} />
                  <Button variant="outline" disabled={busy || !pin || r.folio_status === "Closed"}
                    onClick={() => void decide(r.name, { approve: 1, pin }, false)}>
                    {t("Approve")}
                  </Button>
                  <Button variant="ghost" disabled={busy} onClick={() => setRejecting(r.name)}>
                    {t("Reject")}
                  </Button>
                </>
              ) : onSpot !== r.name ? (
                <Button variant="outline" disabled={busy} onClick={() => startOnSpot(r.name)}>
                  {t("Manager approves now")}
                </Button>
              ) : (
                <>
                  <select className={inputCls} value={sup} onChange={(e) => setSup(e.target.value)}
                    aria-label={t("Manager")}>
                    <option value="">{approvers === null ? t("Loading…") : t("Manager…")}</option>
                    {(approvers || []).map((a) => <option key={a.user} value={a.user}>{a.full_name}</option>)}
                  </select>
                  <input className={`${inputCls} w-24`} type="password" inputMode="numeric" autoComplete="off"
                    value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
                    placeholder={t("Their PIN")} aria-label={t("Manager PIN")} />
                  <Button variant="outline" disabled={busy || !sup || !pin}
                    onClick={() => void decide(r.name, { approve: 1, supervisor: sup, supervisor_pin: pin }, false)}>
                    {t("Approve")}
                  </Button>
                  {approvers !== null && approvers.length === 0 && (
                    <span className="text-xs text-rose-700">
                      {t("No manager with a cashier PIN can approve here yet.")}
                    </span>
                  )}
                </>
              )}
              {r.folio_status === "Closed" && (
                <span className="text-xs text-rose-700">{t("This bill is settled now. Reject it and pass the allowance on an open bill.")}</span>
              )}
            </div>
          )}
          {rejecting === r.name && (
            <div className="mt-2 flex flex-wrap gap-2">
              <input autoFocus className={`${inputCls} min-w-48 flex-1`} value={note}
                onChange={(e) => setNote(e.target.value)} placeholder={t("Why it is rejected (required)")} />
              <Button variant="outline" disabled={busy || !note.trim()}
                onClick={() => void decide(r.name, { approve: 0, note: note.trim() }, true)}>
                {t("Reject")}
              </Button>
              <Button variant="ghost" onClick={() => setRejecting(null)}>{t("Cancel")}</Button>
            </div>
          )}
        </div>
      ))}
      {error && <p className="text-sm text-rose-600">{translate(error)}</p>}
    </div>
  )
}
