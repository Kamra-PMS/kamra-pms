/*  Check-out with company credit control (#238). Before a stay's company
    bill moves to the city ledger, the server checks the company's credit
    limit and overdue bills (kamra.credit.checkout_credit_preview). A
    warning asks the desk to confirm; a block needs Finance or a Hotel
    Admin to override with a reason. check_out re-runs the same check on
    the server, so this dialog is only the explanation - never the gate. */

import { useState, type ReactNode } from "react"
import { ShieldAlert, TriangleAlert, X } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { fmtMoney } from "../lib/money"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export interface CreditCheck {
  ok: boolean
  blocked: boolean
  policy: string
  company: string
  amount: number
  reasons: string[]
  credit_limit: number
  exposure: number
  over_limit_by: number
  overdue_amount: number
  oldest_due_date: string | null
  can_override?: boolean
}

interface Preview {
  reservation: string
  policy: string
  checks: CreditCheck[]
  ok: boolean
  blocked: boolean
  can_override: boolean
}

interface CheckOutResult {
  ok: boolean
  credit_warnings?: { company: string; reasons: string[]; overridden: boolean }[]
}

export const checkOutWithCredit = (reservation: string, credit_override_reason?: string) =>
  call<CheckOutResult>("kamra.api.check_out", {
    reservation,
    ...(credit_override_reason ? { credit_override_reason } : {}),
  })

/** `start(reservation)` checks the company's credit first and checks out
 * straight away when it is fine; otherwise it opens `dialog`. */
export function useCreditCheckout(onDone: () => void) {
  const [preview, setPreview] = useState<Preview | null>(null)

  async function start(reservation: string) {
    let p: Preview | null = null
    try {
      p = await call<Preview>("kamra.credit.checkout_credit_preview", { reservation })
    } catch {
      p = null // the check-out below runs the same check on the server
    }
    if (p && !p.ok) {
      setPreview(p)
      return
    }
    try {
      const out = await checkOutWithCredit(reservation)
      const warned = (out.credit_warnings ?? []).filter((w) => !w.overridden)
      if (warned.length) setNotice(warned)
    } catch (e) {
      const msg = serverError(e)
      if (!msg.includes("CREDIT_BLOCKED")) throw e
      // the server's check found what the preview did not (it moved on
      // meanwhile): show its reason and offer the override
      setPreview({
        reservation,
        policy: "block",
        ok: false,
        blocked: true,
        can_override: p?.can_override ?? false,
        checks: [
          {
            ok: false, blocked: true, policy: "block", company: "",
            amount: 0, reasons: [msg.replace(/^CREDIT_BLOCKED:\s*/, "")],
            credit_limit: 0, exposure: 0, over_limit_by: 0,
            overdue_amount: 0, oldest_due_date: null,
          },
        ],
      })
    }
  }

  const [notice, setNotice] = useState<CheckOutResult["credit_warnings"] | null>(null)

  const dialog: ReactNode = notice ? (
    <div role="status" className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">Checked out with a company credit warning</p>
          <ul className="mt-1 list-disc pl-5">
            {notice.map((w) => w.reasons.map((r) => <li key={w.company + r}>{w.company}: {r}</li>))}
          </ul>
        </div>
        <button className="text-amber-700" onClick={() => setNotice(null)} aria-label="Dismiss">
          <X className="size-4" />
        </button>
      </div>
    </div>
  ) : preview ? (
    <CreditDialog
      preview={preview}
      onClose={() => setPreview(null)}
      onDone={() => {
        setPreview(null)
        onDone()
      }}
    />
  ) : null

  return { start, dialog }
}

function CreditDialog(props: { preview: Preview; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { preview } = props
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const blocked = preview.blocked
  const canGo = !blocked || (preview.can_override && reason.trim().length > 0)

  async function confirm() {
    setBusy(true)
    setErr(null)
    try {
      await checkOutWithCredit(preview.reservation, blocked ? reason.trim() : undefined)
      props.onDone()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={t("Company credit")}
    >
      <div className="absolute inset-0 bg-black/40" onClick={props.onClose} aria-hidden />
      <div className="relative w-full max-w-lg overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div className="flex items-start gap-3">
            {blocked ? (
              <ShieldAlert className="mt-0.5 size-5 text-rose-600" aria-hidden />
            ) : (
              <TriangleAlert className="mt-0.5 size-5 text-amber-600" aria-hidden />
            )}
            <div>
              <h2 className="text-lg font-semibold text-zinc-900">
                {blocked ? t("Company credit is blocked") : t("Company credit warning")}
              </h2>
              <p className="text-sm text-zinc-500">
                {blocked
                  ? t("This bill can't move to the city ledger without an override.")
                  : t("The bill can still move to the city ledger.")}
              </p>
            </div>
          </div>
          <Button variant="ghost" onClick={props.onClose} aria-label={t("Close")}>
            <X className="size-5" />
          </Button>
        </header>

        <div className="space-y-4 px-5 py-4 text-sm">
          {preview.checks
            .filter((c) => !c.ok)
            .map((c) => (
              <div key={c.company || "blocked"} className="rounded-lg border border-zinc-200 p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-zinc-900">{c.company}</span>
                  {c.amount ? (
                    <span className="tabular-nums text-zinc-500">
                      {t("This bill")} {fmtMoney(c.amount)}
                    </span>
                  ) : null}
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-zinc-700">
                  {c.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </div>
            ))}

          {blocked && preview.can_override ? (
            <label className="block">
              <span className="mb-1 block text-zinc-600">
                {t("Reason for the override (logged with your name)")}
              </span>
              <textarea
                className="w-full rounded-lg border border-zinc-300 px-3 py-2"
                rows={3}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                autoFocus
              />
            </label>
          ) : null}
          {blocked && !preview.can_override ? (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-rose-800">
              {t(
                "Ask Finance or a Hotel Admin to override it, take payment from the guest, or have the company settle its account first.",
              )}
            </p>
          ) : null}
          {err ? <p className="text-rose-600">{err}</p> : null}
        </div>

        <footer className="flex justify-end gap-2 border-t border-zinc-100 bg-zinc-50 px-5 py-3">
          <Button variant="outline" onClick={props.onClose} disabled={busy}>
            {t("Cancel")}
          </Button>
          {!blocked || preview.can_override ? (
            <Button onClick={confirm} disabled={busy || !canGo}>
              {busy
                ? t("Checking out…")
                : blocked
                  ? t("Override and check out")
                  : t("Check out anyway")}
            </Button>
          ) : null}
        </footer>
      </div>
    </div>
  )
}
