/*  Change (or remove) the company a stay bills to, mid-stay or at
    check-out. The server (kamra.api.change_stay_company) moves the posted
    charges, runs credit control for the new company and logs who and why;
    this panel only collects the choice. */

import { useEffect, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT, t as translate } from "../lib/i18n"
import { Button } from "./ui/button"

interface Company { name: string; company_name: string }

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function ChangeCompany({ reservation, current, onDone, onCancel }: {
  reservation: string
  /** the Corporate Account the stay bills to now, if any */
  current: string | null
  onDone: () => void
  onCancel: () => void
}) {
  const { t } = useT()
  const [companies, setCompanies] = useState<Company[]>([])
  const [company, setCompany] = useState("")
  const [move, setMove] = useState<"rules" | "guest">("rules")
  const [reason, setReason] = useState("")
  const [override, setOverride] = useState("")
  const [blocked, setBlocked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<{ companies: Company[] }>("kamra.api.booking_options", { property: getCurrentProperty() })
      .then((o) => setCompanies(o.companies.filter((c) => c.name !== current)))
      .catch((e) => setError(serverError(e)))
  }, [current])

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.change_stay_company", {
        reservation, company: company || null, move, reason: reason.trim(),
        override_reason: override.trim() || undefined,
      })
      onDone()
    } catch (e) {
      const msg = serverError(e)
      if (msg.includes("CREDIT_BLOCKED")) setBlocked(true)
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2 rounded-lg border border-zinc-200 bg-white p-3 text-sm">
      <p className="font-medium text-zinc-800">{t("Change the company")}</p>
      <select className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)}
        aria-label={t("New company")}>
        <option value="">{current ? t("No company: the guest pays") : t("Pick a company")}</option>
        {companies.map((c) => <option key={c.name} value={c.name}>{c.company_name}</option>)}
      </select>
      {company && (
        <label className="flex items-start gap-2 text-zinc-700">
          <input type="radio" className="mt-0.5 accent-brand-600" checked={move === "rules"}
            onChange={() => setMove("rules")} />
          {t("Move charges already posted by the new company's billing rules")}
        </label>
      )}
      {current && (
        <label className="flex items-start gap-2 text-zinc-700">
          <input type="radio" className="mt-0.5 accent-brand-600"
            checked={move === "guest" || !company} onChange={() => setMove("guest")} />
          {t("Move everything on the company bill back to the guest")}
        </label>
      )}
      <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder={t("Reason (required, goes on the record)")} />
      {blocked && (
        <textarea className={inputCls} rows={2} maxLength={500} value={override}
          onChange={(e) => setOverride(e.target.value)}
          placeholder={t("Reason for the override (logged with your name)")} />
      )}
      {error && <p className="text-xs text-rose-700">{translate(error)}</p>}
      <p className="text-xs text-zinc-500">
        {t("Charges posted from now on follow the new company's rules. The room rate stays as booked.")}
      </p>
      <div className="flex gap-2">
        <Button variant="outline" disabled={busy || !reason.trim() || (!company && !current)}
          onClick={() => void save()}>
          {busy ? t("Saving…") : t("Change company")}
        </Button>
        <Button variant="ghost" onClick={onCancel}>{t("Cancel")}</Button>
      </div>
    </div>
  )
}
