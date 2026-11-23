/** Recreation desk (#632): gym, pool and spa access for in-house guests,
 *  plus memberships for external customers. Paid in-house access posts to
 *  the guest folio. A membership or a complimentary visit does not.
 *  Walk-in and membership money goes in the till, with a receipt that is
 *  not a tax invoice. Spa treatments and pool sessions are booked here,
 *  never double-booked; members and guests can show a QR pass. */

import { useCallback, useEffect, useState } from "react"
import { fmtMoney, locale } from "../lib/money"
import { todayPlus } from "../lib/stay"
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
  slot_minutes?: number | null
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
  const [planFacilities, setPlanFacilities] = useState<string[]>([])
  const [facCategory, setFacCategory] = useState("Gym")
  const [facSlot, setFacSlot] = useState("0")
  const [mode, setMode] = useState("Cash")
  const [scan, setScan] = useState("")
  const [receipt, setReceipt] = useState<string | null>(null)
  const [tab, setTab] = useState<"desk" | "bookings" | "members" | "report">("desk")
  const payModes = ["Cash", "Card", ...locale().instant_payment_modes]

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
      const out = await run() as { receipt?: string | null } | undefined
      if (out && typeof out === "object" && out.receipt) setReceipt(out.receipt)
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
      <div className="flex flex-wrap gap-2 text-sm" role="tablist">
        {(["desk", "bookings", "members", "report"] as const).map((k) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k}
            className={"rounded-lg border px-3 py-1.5 " + (tab === k ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-300")}
            onClick={() => setTab(k)}>
            {{ desk: t("Desk"), bookings: t("Spa and sessions"), members: t("Members"), report: t("Report") }[k]}
          </button>
        ))}
      </div>
      {receipt && <Receipt name={receipt} onClose={() => setReceipt(null)} />}
      {tab === "bookings" && desk && (
        <Bookings property={property} facilities={desk.facilities} stays={stays}
          customers={desk.customers} admin={admin} onError={setError} onReceipt={setReceipt} />
      )}
      {tab === "members" && desk && (
        <Members customers={desk.customers} onError={setError} onReceipt={setReceipt} />
      )}
      {tab === "report" && <Report property={property} onError={setError} />}
      {tab === "desk" && <>
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
        {guest ? (
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={comp} onChange={(e) => setComp(e.target.checked)} />
            {t("Complimentary")}
          </label>
        ) : (
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}
            aria-label={t("A walk-in pays by")}>
            {payModes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
          </select>
        )}
        <button type="button" disabled={busy || !facility || !who}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
          onClick={() => act(() => call("kamra.recreation.check_in", {
            facility,
            reservation: guest ? who.slice(4) : undefined,
            customer: guest ? undefined : who.slice(4),
            complimentary: comp ? 1 : 0,
            mode,
          }))}>
          {t("Check in")}
        </button>
        <input className={inputCls} value={scan} placeholder={t("Scan a pass (or type its code) and press Enter")}
          aria-label={t("Scan a pass")}
          onChange={(e) => setScan(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || !scan.trim() || !facility) return
            const code = scan.trim()
            setScan("")
            void act(() => call("kamra.recreation.check_in_by_pass", { facility, code }))
          }} />
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
        <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}
          aria-label={t("Paid by")}>
          {payModes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
        </select>
        <button type="button" disabled={busy || !customer || !plan}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
          onClick={() => act(() => call("kamra.recreation.sell_membership", { customer, plan, paid: 1, mode }))}>
          {t("Sell membership")}
        </button>
      </div>
      {admin && (
        <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
          <h2 className="text-sm font-semibold">{t("Add a facility or a plan")}</h2>
          <input className={inputCls} placeholder={t("Facility name")} value={facName}
            onChange={(e) => setFacName(e.target.value)} />
          <select className={inputCls} value={facCategory} onChange={(e) => setFacCategory(e.target.value)}
            aria-label={t("Category")}>
            {["Gym", "Pool", "Spa", "Sauna", "Steam", "Yoga", "Court", "Other"].map((c) =>
              <option key={c} value={c}>{t(c)}</option>)}
          </select>
          <input className={inputCls} placeholder={t("Session price")} value={facPrice}
            onChange={(e) => setFacPrice(e.target.value)} />
          <input className={inputCls} placeholder={t("Session minutes (pool or court slots, 0 for none)")}
            value={facSlot} onChange={(e) => setFacSlot(e.target.value)} />
          <button type="button" disabled={busy || !facName}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => act(async () => {
              await call("kamra.recreation.save_facility", {
                property, facility_name: facName, category: facCategory,
                capacity: facCategory === "Spa" ? 1 : 20,
                access: "Both", price: Number(facPrice) || 0, slot_minutes: Number(facSlot) || 0,
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
          <fieldset className="flex flex-wrap gap-3 text-sm">
            <legend className="mb-1 text-zinc-500">{t("Opens (none ticked: every facility)")}</legend>
            {(desk?.facilities ?? []).map((f) => (
              <label key={f.name} className="flex items-center gap-1.5">
                <input type="checkbox" checked={planFacilities.includes(f.name)}
                  onChange={(e) => setPlanFacilities((cur) => e.target.checked
                    ? [...cur, f.name] : cur.filter((x) => x !== f.name))} />
                {f.facility_name}
              </label>
            ))}
          </fieldset>
          <button type="button" disabled={busy || !planName}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => act(async () => {
              await call("kamra.recreation.save_plan", {
                property, plan_name: planName, period: planPeriod, price: Number(planPrice) || 0,
                facilities: JSON.stringify(planFacilities),
              })
              setPlanName("")
              setPlanFacilities([])
            })}>
            {t("Add plan")}
          </button>
        </div>
      )}
      </>}
    </div>
  )
}

interface Booking {
  name: string; facility_name: string; treatment: string | null; therapist: string | null
  starts_at: string; ends_at: string; who: string; status: string; price: number
}
interface Spa {
  treatments: { name: string; treatment_name: string; duration: number; price: number; facility: string | null }[]
  therapists: { name: string; therapist_name: string }[]
}
interface Slot { starts_at: string; ends_at: string; free: number }

/** Spa treatments (a therapist in a treatment room) and pool / court
 *  sessions. The server refuses a double booking. */
function Bookings({ property, facilities, stays, customers, admin, onError, onReceipt }: {
  property: string
  facilities: Facility[]
  stays: Stay[]
  customers: Customer[]
  admin: boolean
  onError: (e: string) => void
  onReceipt: (name: string) => void
}) {
  const { t } = useT()
  const [day, setDay] = useState(() => todayPlus(0))
  const [rows, setRows] = useState<Booking[]>([])
  const [spa, setSpa] = useState<Spa>({ treatments: [], therapists: [] })
  const [facility, setFacility] = useState(facilities[0]?.name ?? "")
  const [treatment, setTreatment] = useState("")
  const [therapist, setTherapist] = useState("")
  const [time, setTime] = useState("10:00")
  const [who, setWho] = useState("")
  const [slots, setSlots] = useState<Slot[]>([])
  const [newTreatment, setNewTreatment] = useState("")
  const [newMinutes, setNewMinutes] = useState("60")
  const [newPrice, setNewPrice] = useState("0")
  const [newTherapist, setNewTherapist] = useState("")
  const fac = facilities.find((f) => f.name === facility)

  const load = useCallback(() => {
    call<Booking[]>("kamra.recreation.bookings", { property, day }).then(setRows).catch((e) => onError(serverError(e)))
    call<Spa>("kamra.recreation.spa_setup", { property }).then(setSpa).catch(() => {})
    if (facility && fac?.slot_minutes)
      call<Slot[]>("kamra.recreation.facility_slots", { facility, day }).then(setSlots).catch(() => setSlots([]))
    else setSlots([])
  }, [property, day, facility, fac?.slot_minutes, onError])
  useEffect(load, [load])

  async function run(fn: () => Promise<unknown>) {
    onError("")
    try {
      const out = await fn() as { receipt?: string | null } | undefined
      if (out?.receipt) onReceipt(out.receipt)
      load()
    } catch (e) {
      onError(serverError(e))
    }
  }

  const book = (startsAt: string) => run(() => call("kamra.recreation.book", {
    facility, starts_at: startsAt,
    reservation: who.startsWith("res:") ? who.slice(4) : undefined,
    customer: who.startsWith("cus:") ? who.slice(4) : undefined,
    treatment: treatment || undefined, therapist: therapist || undefined,
  }))

  return (
    <div className="space-y-3">
      <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <input type="date" className={inputCls} value={day} onChange={(e) => setDay(e.target.value)} aria-label={t("Day")} />
          <select className={inputCls} value={facility} onChange={(e) => setFacility(e.target.value)} aria-label={t("Facility")}>
            {facilities.map((f) => <option key={f.name} value={f.name}>{f.facility_name}</option>)}
          </select>
          <select className={inputCls} value={who} onChange={(e) => setWho(e.target.value)} aria-label={t("For")}>
            <option value="">{t("Who is it for?")}</option>
            {stays.map((s) => <option key={s.name} value={`res:${s.name}`}>{s.guest_name}</option>)}
            {customers.map((c) => <option key={c.name} value={`cus:${c.name}`}>{c.full_name}</option>)}
          </select>
          <select className={inputCls} value={treatment} onChange={(e) => {
            setTreatment(e.target.value)
            const room = spa.treatments.find((x) => x.name === e.target.value)?.facility
            if (room) setFacility(room)
          }} aria-label={t("Treatment")}>
            <option value="">{t("No treatment (a session)")}</option>
            {spa.treatments.map((x) => (
              <option key={x.name} value={x.name}>{x.treatment_name} · {x.duration} min · {fmtMoney(x.price)}</option>
            ))}
          </select>
          <select className={inputCls} value={therapist} onChange={(e) => setTherapist(e.target.value)} aria-label={t("Therapist")}>
            <option value="">{t("No therapist")}</option>
            {spa.therapists.map((x) => <option key={x.name} value={x.name}>{x.therapist_name}</option>)}
          </select>
          {!slots.length && (
            <input type="time" className={inputCls} value={time} onChange={(e) => setTime(e.target.value)} aria-label={t("Time")} />
          )}
        </div>
        {slots.length ? (
          <div className="flex flex-wrap gap-2">
            {slots.map((sl) => (
              <button key={sl.starts_at} type="button" disabled={!who || sl.free <= 0}
                className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-sm disabled:opacity-40"
                onClick={() => void book(sl.starts_at)}>
                {sl.starts_at.slice(11, 16)} · {t("{n} free", { n: sl.free })}
              </button>
            ))}
          </div>
        ) : (
          <button type="button" disabled={!who || !facility}
            className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
            onClick={() => void book(`${day} ${time}:00`)}>
            {t("Book")}
          </button>
        )}
      </div>
      <ul className="space-y-2">
        {rows.map((b) => (
          <li key={b.name} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-zinc-200 bg-white p-3 text-sm">
            <div>
              <div className="font-medium">{b.starts_at.slice(11, 16)}-{b.ends_at.slice(11, 16)} · {b.who}</div>
              <div className="text-zinc-500">
                {b.facility_name}
                {b.treatment ? ` · ${spa.treatments.find((x) => x.name === b.treatment)?.treatment_name ?? b.treatment}` : ""}
                {b.therapist ? ` · ${spa.therapists.find((x) => x.name === b.therapist)?.therapist_name ?? b.therapist}` : ""}
                {" · "}{t(b.status)}
              </div>
            </div>
            {b.status === "Booked" && (
              <span className="flex gap-3">
                <button type="button" className="underline" onClick={() => void run(() => call("kamra.recreation.arrive", { booking: b.name }))}>{t("Arrived")}</button>
                <button type="button" className="underline" onClick={() => void run(() => call("kamra.recreation.cancel_booking", { booking: b.name, no_show: 1 }))}>{t("No show")}</button>
                <button type="button" className="underline" onClick={() => void run(() => call("kamra.recreation.cancel_booking", { booking: b.name }))}>{t("Cancel")}</button>
              </span>
            )}
          </li>
        ))}
        {!rows.length && <li className="text-sm text-zinc-400">{t("No bookings this day.")}</li>}
      </ul>
      {admin && (
        <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
          <h2 className="text-sm font-semibold">{t("Treatments and therapists")}</h2>
          <div className="grid gap-2 sm:grid-cols-3">
            <input className={inputCls} placeholder={t("Treatment name")} value={newTreatment} onChange={(e) => setNewTreatment(e.target.value)} />
            <input className={inputCls} placeholder={t("Minutes")} value={newMinutes} onChange={(e) => setNewMinutes(e.target.value)} />
            <input className={inputCls} placeholder={t("Price")} value={newPrice} onChange={(e) => setNewPrice(e.target.value)} />
          </div>
          <button type="button" disabled={!newTreatment} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => void run(async () => {
              await call("kamra.recreation.save_treatment", {
                property, treatment_name: newTreatment, duration: Number(newMinutes) || 60,
                price: Number(newPrice) || 0, facility: facility || undefined,
              })
              setNewTreatment("")
            })}>
            {t("Add treatment (booked in the facility picked above)")}
          </button>
          <input className={inputCls} placeholder={t("Therapist name")} value={newTherapist} onChange={(e) => setNewTherapist(e.target.value)} />
          <button type="button" disabled={!newTherapist} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            onClick={() => void run(async () => {
              await call("kamra.recreation.save_therapist", { property, therapist_name: newTherapist })
              setNewTherapist("")
            })}>
            {t("Add therapist")}
          </button>
        </div>
      )}
    </div>
  )
}

interface LedgerRow {
  at: string; kind: string; ref: string; detail: string; status?: string
  charged: number; paid: number; visits_left?: number
}
interface Ledger { full_name: string; entries: LedgerRow[]; charged: number; paid: number; owed: number }

/** One member: their QR pass, renewal and the membership ledger. */
function Members({ customers, onError, onReceipt }: {
  customers: Customer[]
  onError: (e: string) => void
  onReceipt: (name: string) => void
}) {
  const { t } = useT()
  const [customer, setCustomer] = useState("")
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [pass, setPass] = useState<{ code: string; qr: string } | null>(null)

  const load = useCallback(() => {
    setPass(null)
    if (!customer) { setLedger(null); return }
    call<Ledger>("kamra.recreation.membership_ledger", { customer }).then(setLedger).catch((e) => onError(serverError(e)))
  }, [customer, onError])
  useEffect(load, [load])

  const latest = [...(ledger?.entries ?? [])].reverse().find((e) => e.kind !== "Visit")
  return (
    <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4 text-sm">
      <select className={inputCls} value={customer} onChange={(e) => setCustomer(e.target.value)} aria-label={t("Customer")}>
        <option value="">{t("Customer")}</option>
        {customers.map((c) => <option key={c.name} value={c.name}>{c.full_name}</option>)}
      </select>
      {ledger && (
        <>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="rounded-lg border border-zinc-300 px-3 py-2"
              onClick={() => call<{ code: string; qr: string }>("kamra.recreation.entry_pass", { customer })
                .then(setPass).catch((e) => onError(serverError(e)))}>
              {t("Show pass")}
            </button>
            {latest && (
              <button type="button" className="rounded-lg border border-zinc-300 px-3 py-2"
                onClick={() => call<{ receipt?: string }>("kamra.recreation.renew_membership", { membership: latest.ref })
                  .then((out) => { if (out.receipt) onReceipt(out.receipt); load() })
                  .catch((e) => onError(serverError(e)))}>
                {t("Renew {v0}", { v0: latest.detail })}
              </button>
            )}
          </div>
          {pass && (
            <div className="flex items-center gap-3">
              <img src={pass.qr} alt={t("Recreation pass")} className="size-40" />
              <code className="break-all text-xs text-zinc-500">{pass.code}</code>
            </div>
          )}
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-zinc-400">
              <tr><th className="py-1">{t("Date")}</th><th>{t("What")}</th><th className="text-right">{t("Charged")}</th><th className="text-right">{t("Paid")}</th><th /></tr>
            </thead>
            <tbody>
              {ledger.entries.map((e) => (
                <tr key={e.ref} className="border-t border-zinc-100">
                  <td className="py-1.5">{e.at.slice(0, 10)}</td>
                  <td>
                    {t(e.kind)} · {e.detail}
                    {e.visits_left != null ? ` · ${t("{n} visits left", { n: e.visits_left })}` : ""}
                    {e.status && e.status !== "Active" ? ` · ${t(e.status)}` : ""}
                  </td>
                  <td className="text-right tabular-nums">{e.charged ? fmtMoney(e.charged) : "-"}</td>
                  <td className="text-right tabular-nums">{e.paid ? fmtMoney(e.paid) : "-"}</td>
                  <td className="text-right">
                    {e.paid > 0 && <button type="button" className="underline" onClick={() => onReceipt(e.ref)}>{t("Receipt")}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-zinc-600">
            {t("Charged {v0} · paid {v1} · owed {v2}", {
              v0: String(fmtMoney(ledger.charged)), v1: String(fmtMoney(ledger.paid)), v2: String(fmtMoney(ledger.owed)),
            })}
          </p>
        </>
      )}
    </div>
  )
}

interface ReportData {
  from_date: string; to_date: string
  attendance: { total: number; by_day: Record<string, number> }
  by_facility: Record<string, { visits: number; revenue: number }>
  use: { guest: number; external: number }
  revenue: { guest: number; external: number; membership: number; external_total: number }
  memberships: { active: number; expired: number; expiring_soon: { name: string; customer_name: string; plan_name: string; ends_on: string }[] }
}

function Report({ property, onError }: { property: string; onError: (e: string) => void }) {
  const { t } = useT()
  const today = todayPlus(0)
  const [from, setFrom] = useState(today.slice(0, 8) + "01")
  const [to, setTo] = useState(today)
  const [data, setData] = useState<ReportData | null>(null)
  useEffect(() => {
    call<ReportData>("kamra.recreation.report", { property, from_date: from, to_date: to })
      .then(setData).catch((e) => onError(serverError(e)))
  }, [property, from, to, onError])
  return (
    <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4 text-sm">
      <div className="flex flex-wrap gap-2">
        <input type="date" className={inputCls + " max-w-44"} value={from} onChange={(e) => setFrom(e.target.value)} aria-label={t("From")} />
        <input type="date" className={inputCls + " max-w-44"} value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("To")} />
      </div>
      {data && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Figure label={t("Visits")} value={String(data.attendance.total)} />
            <Figure label={t("Hotel guests / outside")} value={`${data.use.guest} / ${data.use.external}`} />
            <Figure label={t("Active memberships")} value={String(data.memberships.active)} />
            <Figure label={t("Expired memberships")} value={String(data.memberships.expired)} />
            <Figure label={t("Revenue from guests (folio)")} value={String(fmtMoney(data.revenue.guest))} />
            <Figure label={t("Walk-in payments")} value={String(fmtMoney(data.revenue.external))} />
            <Figure label={t("Membership fees")} value={String(fmtMoney(data.revenue.membership))} />
            <Figure label={t("Outside customers in all")} value={String(fmtMoney(data.revenue.external_total))} />
          </div>
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-zinc-400">
              <tr><th className="py-1">{t("Facility")}</th><th className="text-right">{t("Visits")}</th><th className="text-right">{t("Revenue")}</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.by_facility).map(([name, f]) => (
                <tr key={name} className="border-t border-zinc-100">
                  <td className="py-1.5">{name}</td>
                  <td className="text-right tabular-nums">{f.visits}</td>
                  <td className="text-right tabular-nums">{fmtMoney(f.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.memberships.expiring_soon.length > 0 && (
            <div>
              <p className="mb-1 text-xs uppercase text-zinc-400">{t("Ending in the next 7 days")}</p>
              <ul>
                {data.memberships.expiring_soon.map((m) => (
                  <li key={m.name}>{m.customer_name} · {m.plan_name} · {m.ends_on}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-zinc-400">
            {t("Attendance by day")}: {Object.entries(data.attendance.by_day).map(([d, n]) => `${d.slice(5)} ${n}`).join(" · ") || "-"}
          </p>
        </>
      )}
    </div>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
    </div>
  )
}

interface ReceiptData {
  number: string; who: string; item: string; date: string; amount: number; paid_by: string; note: string
  property: { property_name?: string; address?: string; city?: string }
}

/** A walk-in's or a membership's receipt, to print. Not a tax invoice. */
function Receipt({ name, onClose }: { name: string; onClose: () => void }) {
  const { t } = useT()
  const [r, setR] = useState<ReceiptData | null>(null)
  useEffect(() => { call<ReceiptData>("kamra.recreation.receipt", { name }).then(setR).catch(() => setR(null)) }, [name])
  if (!r) return null
  return (
    <div className="rounded-2xl border border-zinc-300 bg-white p-4 text-sm print:border-0">
      <div className="font-semibold">{r.property.property_name}</div>
      <div className="text-xs text-zinc-500">{[r.property.address, r.property.city].filter(Boolean).join(", ")}</div>
      <div className="mt-2 flex justify-between"><span>{t("Receipt")} {r.number}</span><span>{r.date}</span></div>
      <div className="mt-1">{r.who}</div>
      <div className="mt-1 flex justify-between"><span>{r.item}</span><b className="tabular-nums">{fmtMoney(r.amount)}</b></div>
      <div className="text-zinc-500">{t("Paid by {v0}", { v0: t(r.paid_by) })}</div>
      <p className="mt-2 text-xs text-zinc-500">{r.note}</p>
      <div className="mt-3 flex gap-3 print:hidden">
        <button type="button" className="underline" onClick={() => window.print()}>{t("Print")}</button>
        <button type="button" className="underline" onClick={onClose}>{t("Close")}</button>
      </div>
    </div>
  )
}
