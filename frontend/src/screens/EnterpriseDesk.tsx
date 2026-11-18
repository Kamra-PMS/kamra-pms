import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { call, getCurrentProperty } from "../lib/api"
import { useT } from "../lib/i18n"

interface Status {
  enterprise: boolean
  edition: string
  pricing_mode: string
  sms_provider: string
  erp_mode: string
  hotel_path: string
}

interface Desk {
  status: Status
  forecast: {
    days: { date: string; on_books: number; predicted: number; premium_pct: number }[]
    extremes: { peak: { date: string; predicted: number } | null; low: { date: string; predicted: number } | null }
    staffing: { attendants: number; cleans: number; arrivals: number }
    note: string
  }
  alerts: { name: string; alert_date: string; message: string; status: string }[]
  plans: { name: string; title: string; area: string; next_due: string; disabled: number }[]
  surveys: { name: string; score: number | null; status: string; comment?: string }[]
}

/** Desk for the Enterprise edition. Community properties get the switch instructions. */
export default function EnterpriseDesk() {
  const { t } = useT()
  const property = getCurrentProperty()
  const [status, setStatus] = useState<Status | null>(null)
  const [desk, setDesk] = useState<Desk | null>(null)
  const [error, setError] = useState("")
  const [guest, setGuest] = useState("")
  const [offers, setOffers] = useState<{ code: string; title: string; detail: string }[]>([])
  const [planTitle, setPlanTitle] = useState("")
  const [planArea, setPlanArea] = useState("")
  const [planDays, setPlanDays] = useState("30")
  const [smsSecret, setSmsSecret] = useState("")
  const [erpSecret, setErpSecret] = useState("")
  const [doorSecret, setDoorSecret] = useState("")
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!property) return
    setError("")
    try {
      const next = await call<Status>("kamra.enterprise.enterprise_status", { property })
      setStatus(next)
      if (next.enterprise) {
        setDesk(await call<Desk>("kamra.enterprise.enterprise_desk", { property, days: 14 }))
      } else {
        setDesk(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Could not load Enterprise."))
    }
  }, [property, t])

  useEffect(() => { load() }, [load])

  async function run(method: string, params: Record<string, unknown>) {
    setBusy(true)
    setError("")
    try {
      await call(method, { property, ...params })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t("That did not work."))
    } finally {
      setBusy(false)
    }
  }

  if (!property) {
    return <p className="p-8 text-sm text-zinc-500">{t("Choose a property first.")}</p>
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold text-zinc-900">{t("Enterprise")}</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {t("Forecast, guest offers, alerts, SMS, surveys, ERPNext, housekeeping priority and maintenance. Community features stay on either way.")}
        </p>
      </header>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {status && !status.enterprise && (
        <section className="rounded-xl border border-zinc-200 bg-white p-4 text-sm text-zinc-700">
          <p>{t("This property is on the Community edition.")}</p>
          <p className="mt-2">
            {t("Turn on Enterprise under Settings. There is no licence key. Nothing you already use is switched off.")}
          </p>
          <Link to="/settings/enterprise" className="mt-3 inline-block font-medium text-brand-700">{t("Open Enterprise settings")}</Link>
        </section>
      )}
      {desk && (
        <>
          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-medium">{t("Occupancy forecast")}</h2>
              <p className="text-xs text-zinc-500">
                {t("Pricing {mode} · SMS {sms} · Books {books}", {
                  mode: desk.status.pricing_mode,
                  sms: desk.status.sms_provider,
                  books: desk.status.erp_mode,
                })}
              </p>
            </div>
            <p className="mt-2 text-sm text-zinc-600">{desk.forecast.note}</p>
            {desk.forecast.extremes.peak && (
              <p className="mt-2 text-sm">
                {t("Busiest {date} at {pct}% · Quietest {quiet} at {low}%", {
                  date: desk.forecast.extremes.peak.date,
                  pct: desk.forecast.extremes.peak.predicted,
                  quiet: desk.forecast.extremes.low?.date || "",
                  low: desk.forecast.extremes.low?.predicted ?? "",
                })}
              </p>
            )}
            <p className="mt-1 text-sm text-zinc-600">
              {t("{attendants} attendants for {cleans} cleans, {arrivals} arrivals today.", desk.forecast.staffing)}
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-start text-xs uppercase text-zinc-400">
                  <tr>
                    <th className="py-1 pe-3 text-start">{t("Date")}</th>
                    <th className="py-1 pe-3 text-end">{t("On the books")}</th>
                    <th className="py-1 pe-3 text-end">{t("Predicted")}</th>
                    <th className="py-1 text-end">{t("Open band")}</th>
                  </tr>
                </thead>
                <tbody>
                  {desk.forecast.days.map((day) => (
                    <tr key={day.date} className="border-t border-zinc-100">
                      <td className="py-1.5 pe-3">{day.date}</td>
                      <td className="py-1.5 pe-3 text-end tabular-nums">{day.on_books}%</td>
                      <td className="py-1.5 pe-3 text-end tabular-nums">{day.predicted}%</td>
                      <td className="py-1.5 text-end tabular-nums">{day.premium_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {desk.status.hotel_path && (
              <p className="mt-3 text-sm">
                <Link to={desk.status.hotel_path} className="text-brand-700">{t("Open the property website")}</Link>
              </p>
            )}
          </section>

          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="font-medium">{t("Alerts")}</h2>
            <ul className="mt-2 space-y-2 text-sm">
              {desk.alerts.map((alert) => (
                <li key={alert.name} className="flex items-start justify-between gap-3">
                  <span>{alert.alert_date}: {alert.message}</span>
                  {alert.status === "Open" && (
                    <button type="button" className="shrink-0 text-brand-700" disabled={busy}
                      onClick={async () => {
                        setBusy(true)
                        setError("")
                        try {
                          await call("kamra.enterprise.acknowledge_alert", { name: alert.name })
                          await load()
                        } catch (err) {
                          setError(err instanceof Error ? err.message : t("That did not work."))
                        } finally {
                          setBusy(false)
                        }
                      }}>
                      {t("Acknowledge")}
                    </button>
                  )}
                </li>
              ))}
              {!desk.alerts.length && <li className="text-zinc-500">{t("No open alerts.")}</li>}
            </ul>
          </section>

          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="font-medium">{t("Guest offers")}</h2>
            <div className="mt-2 flex gap-2">
              <input value={guest} onChange={(e) => setGuest(e.target.value)} placeholder={t("Guest id")}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
              <button type="button" disabled={busy || !guest} className="rounded-lg bg-brand-700 px-3 text-sm text-white disabled:opacity-50"
                onClick={async () => {
                  setBusy(true)
                  try {
                    const out = await call<{ offers: { code: string; title: string; detail: string }[] }>(
                      "kamra.enterprise.guest_recommendations", { property, guest })
                    setOffers(out.offers)
                  } catch (err) {
                    setError(err instanceof Error ? err.message : t("That did not work."))
                  } finally {
                    setBusy(false)
                  }
                }}>{t("Look up")}</button>
            </div>
            <ul className="mt-3 space-y-2 text-sm">
              {offers.map((offer) => (
                <li key={offer.code}><span className="font-medium">{offer.title}.</span> {offer.detail}</li>
              ))}
            </ul>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <h2 className="font-medium">{t("Housekeeping")}</h2>
              <p className="mt-1 text-sm text-zinc-600">{t("Put same-day arrivals first. VIP and morning arrivals become urgent.")}</p>
              <button type="button" disabled={busy} onClick={() => run("kamra.enterprise.prioritize_arrival_cleans", {})}
                className="mt-3 rounded-lg border border-zinc-300 px-3 py-2 text-sm">{t("Prioritize today's cleans")}</button>
            </div>
            <div className="rounded-xl border border-zinc-200 bg-white p-4">
              <h2 className="font-medium">{t("Preventive maintenance")}</h2>
              <div className="mt-2 space-y-2">
                <input value={planTitle} onChange={(e) => setPlanTitle(e.target.value)} placeholder={t("Plan name")}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
                <input value={planArea} onChange={(e) => setPlanArea(e.target.value)} placeholder={t("Area or villa")}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
                <input value={planDays} onChange={(e) => setPlanDays(e.target.value)} placeholder={t("Every N days")}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
                <button type="button" disabled={busy || !planTitle} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                  onClick={() => run("kamra.enterprise.save_maintenance_plan", {
                    title: planTitle, area: planArea, interval_days: Number(planDays) || 30,
                  })}>{t("Save plan")}</button>
              </div>
              <ul className="mt-3 space-y-1 text-sm text-zinc-600">
                {desk.plans.filter((plan) => !plan.disabled).map((plan) => (
                  <li key={plan.name}>{plan.title} · {plan.area} · {plan.next_due}</li>
                ))}
              </ul>
            </div>
          </section>

          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="font-medium">{t("ERPNext sync")}</h2>
            <p className="mt-1 text-sm text-zinc-600">{t("Posts yesterday's closed invoices when accounts are set. CSV export is unchanged.")}</p>
            <button type="button" disabled={busy} onClick={() => run("kamra.enterprise.sync_erpnext", {})}
              className="mt-3 rounded-lg border border-zinc-300 px-3 py-2 text-sm">{t("Sync yesterday")}</button>
          </section>

          <section className="rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="font-medium">{t("Provider secrets")}</h2>
            <p className="mt-1 text-sm text-zinc-600">{t("Stored encrypted. Leave a box blank to keep the current secret.")}</p>
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              <input type="password" value={smsSecret} onChange={(e) => setSmsSecret(e.target.value)} placeholder={t("SMS secret")}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm" autoComplete="off" />
              <input type="password" value={erpSecret} onChange={(e) => setErpSecret(e.target.value)} placeholder={t("ERPNext API secret")}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm" autoComplete="off" />
              <input type="password" value={doorSecret} onChange={(e) => setDoorSecret(e.target.value)} placeholder={t("Encoder secret")}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm" autoComplete="off" />
            </div>
            <button type="button" disabled={busy} className="mt-3 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              onClick={async () => {
                const params: Record<string, unknown> = {}
                if (smsSecret) params.sms_auth = smsSecret
                if (erpSecret) params.erpnext_api_secret = erpSecret
                if (doorSecret) params.door_http_secret = doorSecret
                await run("kamra.enterprise.save_enterprise_secrets", params)
                setSmsSecret(""); setErpSecret(""); setDoorSecret("")
              }}>{t("Save secrets")}</button>
            {!!desk.surveys.length && (
              <p className="mt-4 text-sm text-zinc-600">
                {t("{n} recent surveys", { n: desk.surveys.length })}
              </p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
