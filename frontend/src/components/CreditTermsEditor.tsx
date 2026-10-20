import { useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError, type Row } from "../lib/resource"
import { fmtMoney } from "../lib/money"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"

/** A company's credit terms at the current property: credit limit and
 * payment terms (credit days). Finance / Hotel Admin edit them; the server
 * (kamra.credit.set_company_credit_terms) checks the role and logs it. */

interface Terms {
  company: string
  credit_allowed: boolean
  account: string | null
  credit_limit: number
  credit_days: number
  use_default_credit_days: boolean
  effective_credit_days: number
  default_credit_days: number
  balance: number
  policy: string
  can_edit: boolean
}

const inputCls = "w-full rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"

export default function CreditTermsEditor({ row }: { row: Row; reload: () => void }) {
  const { t } = useT()
  const [terms, setTerms] = useState<Terms | null>(null)
  const [limit, setLimit] = useState("")
  const [days, setDays] = useState("")
  const [useDefault, setUseDefault] = useState(true)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  function apply(t: Terms) {
    setTerms(t)
    setLimit(String(t.credit_limit || 0))
    setDays(String(t.credit_days || 0))
    setUseDefault(t.use_default_credit_days)
  }

  useEffect(() => {
    call<Terms>("kamra.credit.company_credit_terms", {
      company: row.name,
      property: getCurrentProperty(),
    })
      .then(apply)
      .catch((e) => setErr(serverError(e)))
  }, [row.name])

  async function save() {
    setBusy(true)
    setErr(null)
    try {
      apply(
        await call<Terms>("kamra.credit.set_company_credit_terms", {
          company: row.name,
          property: getCurrentProperty(),
          credit_limit: Number(limit || 0),
          credit_days: Number(days || 0),
          use_default_credit_days: useDefault ? 1 : 0,
        }),
      )
      setSaved(true)
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!terms) return err ? <p className="text-xs text-rose-600">{err}</p> : null
  if (!terms.credit_allowed)
    return (
      <div className="border-t border-zinc-200 pt-4">
        <h3 className="text-sm font-medium text-zinc-600">{t("Credit terms")}</h3>
        <p className="mt-0.5 text-xs text-zinc-400">
          {t("Tick Credit allowed and save to bill this company on the city ledger.")}
        </p>
      </div>
    )

  return (
    <div className="border-t border-zinc-200 pt-4">
      <h3 className="text-sm font-medium text-zinc-600">{t("Credit terms at this property")}</h3>
      <p className="mb-2 mt-0.5 text-xs text-zinc-400">
        {t(
          "Bills are due the credit days after the invoice date. Credit control ({policy}) checks the limit and overdue bills at booking and check-out.",
          { policy: terms.policy },
        )}
      </p>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-zinc-500">{t("Credit limit")}</span>
          <input
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            className={inputCls}
            value={limit}
            disabled={!terms.can_edit}
            onChange={(e) => {
              setSaved(false)
              setLimit(e.target.value)
            }}
          />
          <span className="mt-0.5 block text-xs text-zinc-400">{t("0 = no limit")}</span>
        </label>
        <div className="text-sm">
          <span className="mb-1 block text-zinc-500">{t("Payment terms")}</span>
          <label className="mb-1.5 flex items-center gap-2">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={useDefault}
              disabled={!terms.can_edit}
              onChange={(e) => {
                setSaved(false)
                setUseDefault(e.target.checked)
              }}
            />
            {t("Use property default ({n} days)", { n: terms.default_credit_days })}
          </label>
          {!useDefault && (
            <>
              <input
                type="number"
                min="0"
                max="365"
                step="1"
                inputMode="numeric"
                aria-label={t("Credit days")}
                className={inputCls}
                value={days}
                disabled={!terms.can_edit}
                onChange={(e) => {
                  setSaved(false)
                  setDays(e.target.value)
                }}
              />
              <span className="mt-0.5 block text-xs text-zinc-400">
                {t("Credit days after the invoice date - 0 = due on the invoice date")}
              </span>
            </>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        {t("Owes {amount} · terms {n} days", {
          amount: fmtMoney(terms.balance),
          n: terms.effective_credit_days,
        })}
      </p>
      {err ? <p className="mt-2 text-xs text-rose-600">{err}</p> : null}
      {terms.can_edit ? (
        <div className="mt-3 flex items-center gap-2">
          <Button variant="outline" disabled={busy} onClick={save}>
            {busy ? t("Saving…") : t("Save terms")}
          </Button>
          {saved && <span className="text-xs text-emerald-600">{t("Saved")}</span>}
        </div>
      ) : (
        <p className="mt-2 text-xs text-zinc-400">{t("Finance or a Hotel Admin can change these.")}</p>
      )}
    </div>
  )
}
