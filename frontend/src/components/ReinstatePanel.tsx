/*  Undo a checkout made by mistake, the same business day
    (kamra.api.reinstate_checkout). The invoice is cancelled into the
    register, a company bill comes back off the company's account, and the
    guest is in house again in the same room. */

import { useState } from "react"
import { RotateCcw } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export default function ReinstatePanel({ reservation, onDone }: {
  reservation: string
  /** gets what the desk should still do (the stay is no longer checked
   *  out, so this panel goes away) */
  onDone: (warnings: string[]) => void
}) {
  const { t } = useT()
  const { ensureUnlocked } = useCashierAuth()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function go() {
    setBusy(true)
    setErr(null)
    try {
      await ensureUnlocked()
      const out = await call<{ warnings?: string[] }>("kamra.api.reinstate_checkout", { reservation, reason })
      setOpen(false)
      onDone(out.warnings ?? [])
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <RotateCcw className="size-4" />{t("Undo checkout")}
      </Button>
    )
  }
  return (
    <div className="w-full space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="text-amber-900">
        {t("Puts the guest back in house in the same room. The invoice is cancelled (it stays in the cancelled register) and a company bill comes off the company's account. Only before the night audit.")}
      </p>
      <input className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2" value={reason}
        onChange={(e) => setReason(e.target.value)} placeholder={t("Why (e.g. checked out the wrong room)")} />
      {err && <p className="text-xs font-medium text-rose-700">{err}</p>}
      <div className="flex gap-2">
        <Button disabled={busy || !reason.trim()} onClick={() => void go()}>{t("Undo checkout")}</Button>
        <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>{t("Cancel")}</Button>
      </div>
    </div>
  )
}
