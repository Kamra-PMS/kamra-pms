/*  Set or change your own cashier PIN at any time, whether or not the property
    asks PINs of its staff: an approver needs one to approve at someone else's
    till. The server checks the current PIN before changing it. */

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT, t as translate } from "../lib/i18n"
import { Button } from "./ui/button"

const box =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
const digits = (v: string) => v.replace(/\D/g, "").slice(0, 8)

export default function CashierPinDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { t } = useT()
  // null until we know whether there is a PIN to prove first
  const [hasPin, setHasPin] = useState<boolean | null>(null)
  const [current, setCurrent] = useState("")
  const [pin, setPin] = useState("")
  const [again, setAgain] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    call<{ has_pin: boolean; must_reset: boolean }>("kamra.api.cashier_pin_status", { property: getCurrentProperty() })
      .then((s) => setHasPin(s.has_pin && !s.must_reset))
      .catch((e) => setError(serverError(e)))
  }, [])

  const mismatch = again.length >= pin.length && !!again && pin !== again
  const ready = hasPin !== null && (!hasPin || !!current) && pin.length >= 4 && pin === again

  async function save() {
    if (!ready || busy) return
    setBusy(true); setError(null)
    try {
      await call("kamra.api.set_cashier_pin", { pin, current_pin: hasPin ? current : null })
      onSaved()
    } catch (e) {
      setError(serverError(e)); setBusy(false)
    }
  }

  const field = (label: string, value: string, set: (v: string) => void, focus = false) => (
    <label className="flex flex-col gap-1">
      <span className="font-medium text-zinc-600">{label}</span>
      <input autoFocus={focus} className={box} type="password" inputMode="numeric" autoComplete="off"
        value={value} onChange={(e) => set(digits(e.target.value))} />
    </label>
  )

  // on the page body: the top bar's blur would otherwise hold a fixed window inside it
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-zinc-900/40 p-3">
      <form role="dialog" aria-modal="true" aria-label={t("Set my cashier PIN")}
        className="w-full max-w-sm rounded-2xl bg-white shadow-2xl"
        onSubmit={(e) => { e.preventDefault(); void save() }}
        onKeyDown={(e) => e.key === "Escape" && onClose()}>
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <h2 className="text-lg font-bold text-zinc-800">{t("Set my cashier PIN")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Close")}
            className="grid size-9 place-items-center rounded-lg border border-zinc-300 text-zinc-500 hover:bg-zinc-100">
            <X className="size-4" />
          </button>
        </div>
        <div className="space-y-3 p-5 text-sm">
          {hasPin === null ? (!error && <p className="text-zinc-400">{t("Loading…")}</p>) : (
            <>
              {hasPin && field(t("Current PIN"), current, setCurrent, true)}
              {field(t("New PIN"), pin, setPin, !hasPin)}
              {field(t("Repeat new PIN"), again, setAgain)}
              <p className="text-xs text-zinc-400">{t("4 to 8 digits.")}</p>
            </>
          )}
          {mismatch && <p role="alert" className="text-rose-700">{t("The two PINs don't match.")}</p>}
          {error && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-rose-700">{translate(error)}</div>}
        </div>
        <div className="flex justify-end gap-2 border-t border-zinc-200 p-4">
          <Button type="button" variant="ghost" onClick={onClose}>{t("Cancel")}</Button>
          <Button type="submit" disabled={!ready || busy}>{busy ? t("Saving…") : t("Save")}</Button>
        </div>
      </form>
    </div>,
    document.body,
  )
}
