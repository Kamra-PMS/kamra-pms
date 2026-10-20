import { useCallback, useEffect, useState } from "react"
import { Loader2, Wallet } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useCashierAuth } from "../lib/cashierAuth"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

/** The caller's till at a property (kamra.cashier.till_state). */
export interface TillState {
  property: string
  /** does this property take money through tills at all */
  required: boolean
  /** open, or not needed here: money can move */
  open: boolean
  session: string | null
  can_open: boolean
  who_can_open: string[]
  business_date: string
}

/** Load the caller's till; `refresh` after opening it. */
export function useTill(property?: string, enabled = true) {
  const [till, setTill] = useState<TillState | null>(null)
  const refresh = useCallback(async () => {
    try {
      setTill(await call<TillState>("kamra.cashier.my_till", {
        property: property || getCurrentProperty(),
      }))
    } catch {
      setTill(null)
    }
  }, [property])
  useEffect(() => {
    if (enabled) void refresh()
  }, [enabled, refresh])
  return { till, refresh }
}

/* Shown where a sheet is about to take or give back money and the
   operator's till is closed: open it right here (kamra.cashier.open_session,
   the same call as Finance > Cashier) instead of leaving the guest at the
   desk. A role that may not open a till is told who can. */
export default function TillCard(props: {
  till: TillState | null
  /** called once the till is open: reload whatever the sheet shows */
  onOpened: () => void
  /** what the money is for, e.g. "to take the deposit" */
  purpose?: string
}) {
  const { t } = useT()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const [float, setFloat] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const till = props.till
  if (!till || till.open) return null

  async function open() {
    if (!till) return
    setBusy(true)
    setError(null)
    try {
      if (pinStatus?.required) await ensureUnlocked()
      await call("kamra.cashier.open_session", {
        property: till.property,
        opening_float: Number(float || 0),
      })
      props.onOpened()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      data-testid="till-card"
      className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 sm:p-4"
    >
      <h3 className="flex items-center gap-2 font-semibold">
        <Wallet className="size-4 text-amber-700" aria-hidden />
        {t("Your till is closed")}
      </h3>
      {till.can_open ? (
        <>
          <p className="mt-1 text-amber-900">
            {props.purpose
              ? t("Open your till {purpose}. Count the cash in the drawer and enter it as the opening float (0 if it is empty).", { purpose: props.purpose })
              : t("Open your till to take or give back money. Count the cash in the drawer and enter it as the opening float (0 if it is empty).")}
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="block text-xs">
              <span className="mb-1 block text-amber-800">{t("Opening float")}</span>
              <input
                className="w-32 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm"
                type="number"
                min="0"
                inputMode="decimal"
                placeholder="0"
                value={float}
                onChange={(e) => setFloat(e.target.value)}
              />
            </label>
            <Button disabled={busy} onClick={() => void open()}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {t("Open my till")}
            </Button>
          </div>
          <p className="mt-2 text-xs text-amber-800">
            {t("You close it at the end of your shift with a cash count (Finance, Cashier).")}
          </p>
        </>
      ) : (
        <p className="mt-1 text-amber-900">
          {t("Your role can't open a till. Ask {who} to take the money.", {
            who: till.who_can_open.map((r) => t(r)).join(", "),
          })}
        </p>
      )}
      {error && <p role="alert" className="mt-2 text-rose-700">{error}</p>}
    </section>
  )
}
