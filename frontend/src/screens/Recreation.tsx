/** Recreation desk (#632), day one: gym, pool and spa access for in-house
 *  guests, plus memberships for external customers. Paid in-house access
 *  posts to the guest folio. A membership or a complimentary visit does
 *  not. Walk-in cash is recorded on the visit, not as a hotel bill. */

import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty, serverError } from "../lib/api"
import { listResource } from "../lib/resource"
import { useAuth } from "../lib/auth"
import { useT } from "../lib/i18n"

const ADMIN = ["Hotel Admin", "System Manager", "Administrator"]

interface Facility {
  name: string
  facility_name: string
  category: string
  capacity: number
  access: string
  price: number
  status: string
  inside: number
}
interface Visit {
  name: string
  facility_name: string
  who: string
  payment_mode: string
  amount: number
}
interface Plan { name: string; plan_name: string; period: string; price: number; visit_limit: number }
interface Customer { name: string; full_name: string; phone: string | null }
interface Desk {
  facilities: Facility[]
  visits: Visit[]
  plans: Plan[]
  customers: Customer[]
}
interface Stay { name: string; guest_name: string }

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function Recreation() {
  const { t } = useT()
  const { roles } = useAuth()
  const admin = roles.some((r) => ADMIN.includes(r))
  const property = getCurrentProperty()
  const [desk, setDesk] = useState<Desk | null>(null)
  const [stays, setStays] = useState<Stay[]>([])
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [facility, setFacility] = useState("")
  const [who, setWho] = useState("")
  const [comp, setComp] = useState(false)
  const [customerName, setCustomerName] = useState("")
  const [plan, setPlan] = useState("")
  const [customer, setCustomer] = useState("")
  const [facName, setFacName] = useState("")
  const [facPrice, setFacPrice] = useState("0")
  const [planName, setPlanName] = useState("")
  const [planPrice, setPlanPrice] = useState("0")
  const [planPeriod, setPlanPeriod] = useState("Month")

  const load = useCallback(() => {
    call<Desk>("kamra.recreation.desk", { property })
      .then((d) => {
        setDesk(d)
        setFacility((cur) => cur || d.facilities[0]?.name || "")
        setPlan((cur) => cur || d.plans[0]?.name || "")
        setCustomer((cur) => cur || d.customers[0]?.name || "")
      })
      .catch((e) => setError(serverError(e)))
    listResource("Reservation", {
      fields: ["name", "guest_name"],
      filters: [["property", "=", property], ["status", "=", "Checked In"]],
      orderBy: "guest_name asc",
      limit: 100,
    }).then((rows) => setStays(rows as unknown as Stay[])).catch(() => {})
  }, [property])
  useEffect(() => { load() }, [load])

  async function act(run: () => Promise<unknown>) {
    setBusy(true)
    setError("")
    try {
      await run()
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const guest = who.startsWith("res:")
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <h1 className="text-lg font-semibold text-zinc-900">{t("Recreation")}</h1>
      <p className="text-sm text-zinc-500">
        {t("In-house guests can use the gym free or on the folio. External customers come in on a membership or pay cash at the desk. Cash is not a hotel invoice.")}
      </p>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {(desk?.facilities ?? []).map((f) => (
          <button type="button" key={f.name} onClick={() => setFacility(f.name)}
            className={"rounded-2xl border p-3 text-start text-sm " +
              (facility === f.name ? "border-zinc-900" : "border-zinc-200 bg-white")}>
            <div className="font-medium">{f.facility_name}</div>
            <div className="text-zinc-500">
              {f.category} · {f.inside}/{f.capacity} · {f.access}
              {f.price ? ` · ${f.price}` : ""}
              {f.status !== "Open" ? ` · ${f.status}` : ""}
            </div>
          </button>
        ))}
      </div>
      <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
        <select className={inputCls} value={who} onChange={(e) => setWho(e.target.value)}>
          <option value="">{t("Who is coming in?")}</option>
          {stays.map((s) => (
            <option key={s.name} value={`res:${s.name}`}>{s.guest_name}</option>
          ))}
          {(desk?.customers ?? []).map((c) => (
            <option key={c.name} value={`cus:${c.name}`}>{c.full_name}</option>
          ))}
        </select>
        {guest && (
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={comp} onChange={(e) => setComp(e.target.checked)} />
            {t("Complimentary")}
          </label>
        )}
        <button type="button" disabled={busy || !facility || !who}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
          onClick={() => act(() => call("kamra.recreation.check_in", {
            facility,
            reservation: guest ? who.slice(4) : undefined,
            customer: guest ? undefined : who.slice(4),
            complimentary: comp ? 1 : 0,
          }))}>
          {t("Check in")}
        </button>
      </div>
      <ul className="space-y-2">
        {(desk?.visits ?? []).map((v) => (
          <li key={v.name} className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white p-3 text-sm">
            <div>
              <div className="font-medium">{v.who}</div>
              <div className="text-zinc-500">{v.facility_name} · {v.payment_mode}{v.amount ? ` · ${v.amount}` : ""}</div>
            </div>
            <button type="button" disabled={busy} className="text-sm underline"
              onClick={() => act(() => call("kamra.recreation.check_out", { visit: v.name }))}>
              {t("Check out")}
            </button>
          </li>
        ))}
      </ul>
      <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
        <h2 className="text-sm font-semibold">{t("Membership")}</h2>
        <input className={inputCls} placeholder={t("Customer name")} value={customerName}
          onChange={(e) => setCustomerName(e.target.value)} />
        <button type="button" disabled={busy || !customerName}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          onClick={() => act(async () => {
            await call("kamra.recreation.register_customer", { property, full_name: customerName })
            setCustomerName("")
          })}>
          {t("Add customer")}
        </button>
        <select className={inputCls} value={customer} onChange={(e) => setCustomer(e.target.value)}>
          <option value="">{t("Customer")}</option>
          {(desk?.customers ?? []).map((c) => (
            <option key={c.name} value={c.name}>{c.full_name}</option>
          ))}
        </select>
        <select className={inputCls} value={plan} onChange={(e) => setPlan(e.target.value)}>
          <option value="">{t("Plan")}</option>
          {(desk?.plans ?? []).map((p) => (
            <option key={p.name} value={p.name}>{p.plan_name} · {p.period} · {p.price}</option>
          ))}
        </select>
        <button type="button" disabled={busy || !customer || !plan}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
          onClick={() => act(() => call("kamra.recreation.sell_membership", { customer, plan, paid: 1 }))}>
          {t("Sell membership")}
        </button>
      </div>
      {admin && (
        <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
          <h2 className="text-sm font-semibold">{t("Add a facility or a plan")}</h2>
          <input className={inputCls} placeholder={t("Facility name")} value={facName}
            onChange={(e) => setFacName(e.target.value)} />
          <input className={inputCls} placeholder={t("Session price")} value={facPrice}
            onChange={(e) => setFacPrice(e.target.value)} />
          <button type="button" disabled={busy || !facName}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => act(async () => {
              await call("kamra.recreation.save_facility", {
                property, facility_name: facName, category: "Gym", capacity: 20,
                access: "Both", price: Number(facPrice) || 0,
              })
              setFacName("")
            })}>
            {t("Add facility")}
          </button>
          <input className={inputCls} placeholder={t("Plan name")} value={planName}
            onChange={(e) => setPlanName(e.target.value)} />
          <select className={inputCls} value={planPeriod} onChange={(e) => setPlanPeriod(e.target.value)}>
            <option value="Day">{t("Day")}</option>
            <option value="Week">{t("Week")}</option>
            <option value="Month">{t("Month")}</option>
            <option value="Year">{t("Year")}</option>
          </select>
          <input className={inputCls} placeholder={t("Plan price")} value={planPrice}
            onChange={(e) => setPlanPrice(e.target.value)} />
          <button type="button" disabled={busy || !planName}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => act(async () => {
              await call("kamra.recreation.save_plan", {
                property, plan_name: planName, period: planPeriod, price: Number(planPrice) || 0,
              })
              setPlanName("")
            })}>
            {t("Add plan")}
          </button>
        </div>
      )}
    </div>
  )
}
