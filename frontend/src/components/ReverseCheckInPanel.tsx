/*  Undo a check-in made by mistake, the same business day and before
    anything is on the bill (kamra.api.reverse_check_in, OPERA's Reverse
    Check In). The stay goes back to arrival with its room; the room is
    released and marked dirty for housekeeping to inspect. */

import { useState } from "react"
import { Undo2 } from "lucide-react"
import { call } from "../lib/api"
import { keyResultMessage } from "../lib/keyNotice"
import { serverError } from "../lib/resource"
import { useCashierAuth } from "../lib/cashierAuth"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

export default function ReverseCheckInPanel({ reservation, onDone }: {
  reservation: string
  /** gets what the lock system said, if anything (the stay is no longer
   *  checked in, so this panel goes away) */
  onDone: (keyMessage: string | null) => void
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
      const out = await call<{ key_result?: { message?: string | null } | null }>(
        "kamra.api.reverse_check_in", { reservation, reason })
      setOpen(false)
      onDone(keyResultMessage(out))
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Undo2 className="size-4" />{t("Undo check-in")}
      </Button>
    )
  }
  return (
    <div className="w-full space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="text-amber-900">
        {t("Puts the booking back to arrival with its room. The room is released and marked dirty for housekeeping to check. Only today, and only while nothing is on the bill.")}
      </p>
      <input className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2" value={reason}
        onChange={(e) => setReason(e.target.value)} placeholder={t("Why (e.g. checked in the wrong guest)")} />
      {err && <p className="text-xs font-medium text-rose-700">{err}</p>}
      <div className="flex gap-2">
        <Button disabled={busy || !reason.trim()} onClick={() => void go()}>{t("Undo check-in")}</Button>
        <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>{t("Cancel")}</Button>
      </div>
    </div>
  )
}
