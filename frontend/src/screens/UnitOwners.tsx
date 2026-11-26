/** Unit owners (#639). Hotel Admin links an owner to units and logins.
 *  The owner signs in and sees only those units: a calendar, occupancy,
 *  bookings, room revenue and a monthly statement. Manage can also hold
 *  or book one of their own units and set the rate of a unit type they
 *  own outright. An owner can hold whole unit types. Guest name and phone stay hidden unless the admin
 *  turns Show guest contact on. */

import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty, serverError, setCurrentProperty } from "../lib/api"
import { fmtAmount } from "../lib/money"
import { useAuth } from "../lib/auth"
import { tn, useT } from "../lib/i18n"

const ADMIN = ["Hotel Admin", "System Manager", "Administrator"]

interface OwnerRow {
  name: string
  owner_name: string
  access: string
  show_guest_contact: number
  commission_percent: number
  units: string[]
  unit_commission?: Record<string, number>
  room_types?: string[]
  users: string[]
  costs?: { posting_date: string; room: string | null; description: string; amount: number }[]
}
interface RoomRow { name: string; room_number: string }
interface Desk {
  owners: OwnerRow[]
  rooms: RoomRow[]
  room_types?: { name: string; room_type_name: string }[]
}
interface Booking {
  reservation: string
  room_number: string
  status: string
  check_in: string
  check_out: string
  guest: string
  phone: string | null
}
interface Hold {
  name: string
  room: string
  room_number: string
  from_date: string
  to_date: string
  reason: string
  mine: boolean
}
interface Portal {
  owner_name: string
  access: string
  show_guest_contact: boolean
  occupancy_pct: number
  room_nights: number
  revenue: number
  units: { room: string; room_number: string; occupancy_status: string; revenue?: number }[]
  bookings: Booking[]
  blocks: Hold[]
  priceable_types?: { room_type: string; name: string }[]
}
interface Statement {
  from_date: string
  to_date: string
  room_nights: number
  revenue: number
  commission: number
  costs: number
  payout: number
  lines?: { owner_name: string; room_number: string; room_nights: number; revenue: number;
    commission_percent: number; commission: number }[]
  cost_lines?: { date: string; description: string; amount: number }[]
}

interface Overview {
  from_date: string
  to_date: string
  properties: {
    property: string
    property_name: string
    currency: string
    currency_symbol: string
    units: number
    occupancy_pct: number
    room_nights: number
    revenue: number
    statement?: Statement
  }[]
  totals: {
    units: number
    room_nights: number
    occupancy_pct: number
    currency: string | null
    revenue: number | null
    statement?: { revenue: number | null; commission: number | null; costs: number | null; payout: number | null }
  }
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function iso(offset: number) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return z.toISOString().slice(0, 10)
}

export default function UnitOwners() {
  const { t } = useT()
  const { roles } = useAuth()
  const admin = roles.some((r) => ADMIN.includes(r))
  const mine = roles.includes("Owner")
  const [tab, setTab] = useState(admin ? "desk" : "portal")

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <h1 className="text-lg font-semibold text-zinc-900">{t("Unit owners")}</h1>
      {admin && mine && (
        <div className="flex gap-2">
          <Tab on={tab === "desk"} onClick={() => setTab("desk")}>{t("Owners")}</Tab>
          <Tab on={tab === "portal"} onClick={() => setTab("portal")}>{t("My units")}</Tab>
        </div>
      )}
      {tab === "desk" && admin ? <DeskPanel /> : <OwnerPortal />}
    </div>
  )
}

function Tab({ on, children, onClick }: { on: boolean; children: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className={on
        ? "rounded-full bg-zinc-900 px-3 py-1 text-sm text-white"
        : "rounded-full border border-zinc-300 px-3 py-1 text-sm text-zinc-700"}>
      {children}
    </button>
  )
}

function DeskPanel() {
  const { t } = useT()
  const property = getCurrentProperty()
  const [desk, setDesk] = useState<Desk | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState("")
  const [ownerName, setOwnerName] = useState("")
  const [access, setAccess] = useState("Read only")
  const [show, setShow] = useState(false)
  const [commission, setCommission] = useState("0")
  const [rooms, setRooms] = useState<string[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [unitCut, setUnitCut] = useState<Record<string, string>>({})
  const [users, setUsers] = useState("")
  const [costFor, setCostFor] = useState("")
  const [cost, setCost] = useState({ date: new Date().toISOString().slice(0, 10), description: "", amount: "" })

  const load = useCallback(() => {
    call<Desk>("kamra.owners.desk", { property })
      .then(setDesk)
      .catch((e) => setError(serverError(e)))
  }, [property])
  useEffect(() => { load() }, [load])

  function edit(row: OwnerRow) {
    setName(row.name)
    setOwnerName(row.owner_name)
    setAccess(row.access)
    setShow(!!row.show_guest_contact)
    setCommission(String(row.commission_percent ?? 0))
    setRooms(row.units)
    setTypes(row.room_types ?? [])
    setUnitCut(Object.fromEntries(Object.entries(row.unit_commission ?? {}).map(([k, v]) => [k, String(v)])))
    setUsers(row.users.join("\n"))
  }

  async function save() {
    setBusy(true)
    setError("")
    try {
      await call("kamra.owners.save_owner", {
        property,
        name: name || undefined,
        owner_name: ownerName,
        access,
        show_guest_contact: show ? 1 : 0,
        commission_percent: Number(commission) || 0,
        rooms,
        room_types: types,
        unit_commission: Object.fromEntries(Object.entries(unitCut)
          .filter(([room, v]) => rooms.includes(room) && v !== "").map(([room, v]) => [room, Number(v)])),
        users: users.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean),
      })
      setName("")
      setOwnerName("")
      setUsers("")
      setRooms([])
      setTypes([])
      setUnitCut({})
      setShow(false)
      setCommission("0")
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        {t("Each owner gets a login that sees only their units. Guest contact stays off unless you turn it on. Identity documents are never shown.")}
      </p>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
        <input className={inputCls} placeholder={t("Owner name")} value={ownerName}
          onChange={(e) => setOwnerName(e.target.value)} />
        <select className={inputCls} value={access} onChange={(e) => setAccess(e.target.value)}>
          <option value="Read only">{t("Read only")}</option>
          <option value="Manage">{t("Manage")}</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-zinc-700">
          <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
          {t("Show guest name and phone")}
        </label>
        <input className={inputCls} inputMode="decimal" placeholder={t("Commission %")}
          value={commission} onChange={(e) => setCommission(e.target.value)} />
        <p className="text-xs text-zinc-500">
          {t("A new email is created as a login. Set the password in Staff & Access. Manage can hold and book their own units and price a unit type they own outright. Read only cannot.")}
        </p>
        <div className="flex flex-wrap gap-2">
          {(desk?.rooms ?? []).map((r) => (
            <label key={r.name} className="flex items-center gap-1 rounded-full border border-zinc-200 px-2 py-1 text-sm">
              <input type="checkbox" checked={rooms.includes(r.name)}
                onChange={(e) => setRooms(e.target.checked
                  ? [...rooms, r.name]
                  : rooms.filter((x) => x !== r.name))} />
              {r.room_number}
              {rooms.includes(r.name) && (
                <input className="w-14 rounded border border-zinc-200 px-1 text-xs" inputMode="decimal"
                  placeholder="%" aria-label={t("Commission % for {unit}", { unit: r.room_number })}
                  value={unitCut[r.name] ?? ""}
                  onChange={(e) => setUnitCut({ ...unitCut, [r.name]: e.target.value })} />
              )}
            </label>
          ))}
        </div>
        {(desk?.room_types ?? []).length > 0 && (
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">{t("Or whole unit types: every unit of the type, including ones added later.")}</p>
            <div className="flex flex-wrap gap-2">
              {(desk?.room_types ?? []).map((rt) => (
                <label key={rt.name} className="flex items-center gap-1 rounded-full border border-zinc-200 px-2 py-1 text-sm">
                  <input type="checkbox" checked={types.includes(rt.name)}
                    onChange={(e) => setTypes(e.target.checked ? [...types, rt.name] : types.filter((x) => x !== rt.name))} />
                  {rt.room_type_name || rt.name}
                </label>
              ))}
            </div>
          </div>
        )}
        <textarea className={inputCls} rows={2} placeholder={t("Login emails, one per line")}
          value={users} onChange={(e) => setUsers(e.target.value)} />
        <button type="button" disabled={busy || !ownerName || (!rooms.length && !types.length)}
          onClick={save}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          {name ? t("Save owner") : t("Add owner")}
        </button>
      </div>
      <ul className="space-y-2">
        {(desk?.owners ?? []).map((row) => (
          <li key={row.name} className="flex flex-wrap items-center justify-between rounded-2xl border border-zinc-200 bg-white p-3 text-sm">
            <div>
              <div className="font-medium">{row.owner_name}</div>
              <div className="text-zinc-500">
                {t(row.access)} · {row.commission_percent}% · {row.units.length} {t("units")}{row.room_types?.length ? ` + ${row.room_types.length} ${t("unit types")}` : ""} · {row.users.join(", ")}
                {row.show_guest_contact ? ` · ${t("guest contact on")}` : ""}
              </div>
            </div>
            <div className="flex gap-3">
              <button type="button" className="text-sm text-zinc-700 underline" onClick={() => edit(row)}>
                {t("Edit")}
              </button>
              <button type="button" className="text-sm text-zinc-700 underline"
                onClick={() => setCostFor(costFor === row.name ? "" : row.name)}>
                {t("Add cost")}
              </button>
            </div>
            {costFor === row.name && (
              <div className="mt-2 flex w-full flex-wrap gap-2">
                <input type="date" className={inputCls + " max-w-40"} value={cost.date}
                  onChange={(e) => setCost({ ...cost, date: e.target.value })} />
                <input className={inputCls + " max-w-60"} placeholder={t("What the cost is for")}
                  value={cost.description} onChange={(e) => setCost({ ...cost, description: e.target.value })} />
                <input className={inputCls + " max-w-28"} inputMode="decimal" placeholder={t("Amount")}
                  value={cost.amount} onChange={(e) => setCost({ ...cost, amount: e.target.value })} />
                <button type="button" disabled={busy || !cost.description.trim() || !Number(cost.amount)}
                  className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
                  onClick={async () => {
                    setBusy(true); setError("")
                    try {
                      await call("kamra.owners.add_owner_cost", {
                        owner: row.name, posting_date: cost.date,
                        description: cost.description.trim(), amount: Number(cost.amount),
                      })
                      setCostFor(""); setCost({ ...cost, description: "", amount: "" })
                      load()
                    } catch (e) { setError(serverError(e)) } finally { setBusy(false) }
                  }}>
                  {t("Save cost")}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function daysBetween(from: string, to: string): string[] {
  const startText = from <= to ? from : to
  const endText = from <= to ? to : from
  const out: string[] = []
  const cursor = new Date(`${startText}T12:00:00`)
  const end = new Date(`${endText}T12:00:00`)
  while (cursor <= end && out.length < 42) {
    const z = new Date(cursor.getTime() - cursor.getTimezoneOffset() * 60000)
    out.push(z.toISOString().slice(0, 10))
    cursor.setDate(cursor.getDate() + 1)
  }
  return out
}

function covers(day: string, start: string, end: string) {
  return start <= day && day < end
}

/** One property's portal, with "All my properties" beside it once the
 *  owner has units at more than one. */
function OwnerPortal() {
  const { t } = useT()
  const [many, setMany] = useState(false)
  const [all, setAll] = useState(false)
  useEffect(() => {
    call<Overview>("kamra.owners.my_overview", {})
      .then((o) => setMany(o.properties.length > 1))
      .catch(() => setMany(false))
  }, [])
  return (
    <div className="space-y-4">
      {many && (
        <div className="flex gap-2">
          <Tab on={!all} onClick={() => setAll(false)}>{t("This property")}</Tab>
          <Tab on={all} onClick={() => setAll(true)}>{t("All my properties")}</Tab>
        </div>
      )}
      {all ? (
        <AllPropertiesPanel onOpen={(p) => {
          setCurrentProperty(p)
          // the header switcher follows (AppShell listens)
          window.dispatchEvent(new CustomEvent("kamra:property", { detail: p }))
          setAll(false)
        }} />
      ) : <PortalPanel />}
    </div>
  )
}

/** #713: every property the owner has units at, side by side, and one
 *  month's statement for all of them. Totals only when the currencies match. */
function AllPropertiesPanel({ onOpen }: { onOpen: (property: string) => void }) {
  const { t } = useT()
  const [from, setFrom] = useState(iso(0))
  const [to, setTo] = useState(iso(30))
  const [month, setMonth] = useState(iso(0).slice(0, 7))
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    setError("")
    call<Overview>("kamra.owners.my_overview", { from_date: from, to_date: to, month })
      .then(setData)
      .catch((e) => setError(serverError(e)))
  }, [from, to, month])

  const money = (n: number | null | undefined, currency: string | null, symbol = "") =>
    n == null ? t("Mixed currencies") : `${symbol}${fmtAmount(n, currency)}`
  const sym = data?.properties.find((p) => p.currency === data.totals.currency)?.currency_symbol ?? ""

  function download(o: Overview) {
    const rows = [
      ["property", "currency", "unit", "room_nights", "revenue", "commission_percent", "commission"],
      ...o.properties.flatMap((p) => (p.statement?.lines ?? []).map((l) => [
        `"${p.property_name.replace(/"/g, '""')}"`, p.currency, l.room_number, String(l.room_nights),
        String(l.revenue), String(l.commission_percent), String(l.commission)])),
      [],
      ["property", "currency", "cost_date", "description", "amount"],
      ...o.properties.flatMap((p) => (p.statement?.cost_lines ?? []).map((c) => [
        `"${p.property_name.replace(/"/g, '""')}"`, p.currency, c.date,
        `"${c.description.replace(/"/g, '""')}"`, String(c.amount)])),
      [],
      ["property", "currency", "revenue", "commission", "costs", "payout"],
      ...o.properties.map((p) => [`"${p.property_name.replace(/"/g, '""')}"`, p.currency,
        String(p.statement?.revenue ?? 0), String(p.statement?.commission ?? 0),
        String(p.statement?.costs ?? 0), String(p.statement?.payout ?? 0)]),
    ]
    const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = `owner-statement-all-${month}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input type="date" aria-label={t("From")} className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} />
        <input type="date" aria-label={t("To")} className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-2">
            <Stat label={t("Occupancy")} value={`${data.totals.occupancy_pct}%`} />
            <Stat label={t("Room nights")} value={String(data.totals.room_nights)} />
            <Stat label={t("Room revenue")} value={money(data.totals.revenue, data.totals.currency, sym)} />
          </div>
          <ul className="space-y-2">
            {data.properties.map((p) => (
              <li key={p.property}>
                <button type="button" onClick={() => onOpen(p.property)}
                  className="w-full rounded-2xl border border-zinc-200 bg-white p-3 text-start hover:border-zinc-400">
                  <div className="text-sm font-medium">{p.property_name}</div>
                  <div className="text-sm text-zinc-500">
                    {tn(p.units, "{n} unit", "{n} units")} · {p.occupancy_pct}% · {tn(p.room_nights, "{n} room night", "{n} room nights")}
                    {" · "}{money(p.revenue, p.currency, p.currency_symbol)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold">{t("Statement for all properties")}</h2>
            <p className="text-xs text-zinc-500">
              {t("Room revenue per unit, minus commission and your costs that month. Guest names are not on this file.")}
            </p>
            <input type="month" aria-label={t("Month")} className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <Stat label={t("Room revenue")} value={money(data.totals.statement?.revenue, data.totals.currency, sym)} />
              <Stat label={t("Commission")} value={money(data.totals.statement?.commission, data.totals.currency, sym)} />
              <Stat label={t("Costs")} value={money(data.totals.statement?.costs, data.totals.currency, sym)} />
              <Stat label={t("Payout")} value={money(data.totals.statement?.payout, data.totals.currency, sym)} />
            </div>
            <ul className="space-y-1 text-sm">
              {data.properties.map((p) => (
                <li key={p.property} className="flex justify-between gap-2">
                  <span className="truncate">{p.property_name}</span>
                  <span className="tabular-nums">{t("Payout")}: {money(p.statement?.payout ?? 0, p.currency, p.currency_symbol)}</span>
                </li>
              ))}
            </ul>
            <button type="button" className="underline text-sm" onClick={() => download(data)}>
              {t("Download statement")}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function PortalPanel() {
  const { t } = useT()
  const property = getCurrentProperty()
  const [from, setFrom] = useState(iso(0))
  const [to, setTo] = useState(iso(30))
  const [data, setData] = useState<Portal | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [holdRoom, setHoldRoom] = useState("")
  const [holdFrom, setHoldFrom] = useState(iso(1))
  const [holdTo, setHoldTo] = useState(iso(3))
  const [month, setMonth] = useState(iso(0).slice(0, 7))
  const [book, setBook] = useState({ room: "", from: iso(1), to: iso(3), guest: "", adults: "1" })
  const [price, setPrice] = useState({ type: "", from: iso(1), to: iso(7), rate: "" })
  const [statement, setStatement] = useState<Statement | null>(null)

  const load = useCallback(() => {
    call<Portal>("kamra.owners.my_portal", { property, from_date: from, to_date: to })
      .then((portal) => {
        setData(portal)
        setHoldRoom((cur) => cur || portal.units[0]?.room || "")
      })
      .catch((e) => setError(serverError(e)))
  }, [property, from, to])
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

  const days = daysBetween(from, to)
  const blocks = data?.blocks ?? []
  const manage = data?.access === "Manage"

  function download(row: Statement) {
    const lines = [
      ["from", row.from_date],
      ["to", row.to_date],
      [],
      ["unit", "room_nights", "revenue", "commission_percent", "commission"],
      ...(row.lines ?? []).map((l) => [l.room_number, String(l.room_nights), String(l.revenue),
        String(l.commission_percent), String(l.commission)]),
      [],
      ["cost_date", "description", "amount"],
      ...(row.cost_lines ?? []).map((c) => [c.date, `"${c.description.replace(/"/g, '""')}"`, String(c.amount)]),
      [],
      ["room_nights", String(row.room_nights)],
      ["revenue", String(row.revenue)],
      ["commission", String(row.commission)],
      ["costs", String(row.costs)],
      ["payout", String(row.payout)],
    ]
    const blob = new Blob([lines.map((line) => line.join(",")).join("\n")], { type: "text/csv" })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = `owner-statement-${row.from_date}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} />
        <input type="date" className={inputCls} value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {data && (
        <>
          <p className="text-sm text-zinc-500">
            {data.owner_name} · {t(data.access)}
            {data.show_guest_contact ? "" : ` · ${t("Guest names are hidden")}`}
          </p>
          <div className="grid grid-cols-3 gap-2">
            <Stat label={t("Occupancy")} value={`${data.occupancy_pct}%`} />
            <Stat label={t("Room nights")} value={String(data.room_nights)} />
            <Stat label={t("Room revenue")} value={String(data.revenue)} />
          </div>
          {data.units.map((unit) => (
            <section key={unit.room} className="rounded-2xl border border-zinc-200 bg-white p-3">
              <div className="mb-2 text-sm font-medium">
                {unit.room_number}
                <span className="ms-2 font-normal text-zinc-500">{unit.occupancy_status}</span>
              </div>
              <div className="grid grid-cols-7 gap-1">
                {days.map((day) => {
                  const stay = data.bookings.some((b) => b.room_number === unit.room_number && covers(day, b.check_in, b.check_out))
                  const held = blocks.some((b) => b.room === unit.room && covers(day, b.from_date, b.to_date))
                  return (
                    <div key={day} title={day}
                      className={"rounded px-1 py-1 text-center text-[10px] " +
                        (stay ? "bg-zinc-900 text-white" : held ? "bg-amber-100 text-amber-900" : "bg-zinc-100 text-zinc-500")}>
                      {day.slice(8)}
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
          <ul className="space-y-2">
            {data.bookings.map((b) => (
              <li key={b.reservation} className="rounded-2xl border border-zinc-200 bg-white p-3 text-sm">
                <div className="font-medium">{b.room_number} · {b.guest}</div>
                <div className="text-zinc-500">
                  {b.check_in} – {b.check_out} · {b.status}
                  {b.phone ? ` · ${b.phone}` : ""}
                </div>
              </li>
            ))}
          </ul>
          {manage && (
            <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
              <h2 className="text-sm font-semibold">{t("Hold a unit")}</h2>
              <p className="text-xs text-zinc-500">
                {t("This takes one of your units off sale. It does not create a guest booking or change a price.")}
              </p>
              <select className={inputCls} value={holdRoom} onChange={(e) => setHoldRoom(e.target.value)}>
                {data.units.map((unit) => (
                  <option key={unit.room} value={unit.room}>{unit.room_number}</option>
                ))}
              </select>
              <div className="flex gap-2">
                <input type="date" className={inputCls} value={holdFrom} onChange={(e) => setHoldFrom(e.target.value)} />
                <input type="date" className={inputCls} value={holdTo} onChange={(e) => setHoldTo(e.target.value)} />
              </div>
              <button type="button" disabled={busy || !holdRoom}
                className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
                onClick={() => act(() => call("kamra.owners.block_unit", {
                  property, room: holdRoom, from_date: holdFrom, to_date: holdTo,
                }))}>
                {t("Hold these dates")}
              </button>
              <ul className="space-y-1">
                {blocks.filter((b) => b.mine).map((b) => (
                  <li key={b.name} className="flex items-center justify-between text-sm">
                    <span>{b.room_number} · {b.from_date} – {b.to_date}</span>
                    <button type="button" className="underline" disabled={busy}
                      onClick={() => act(() => call("kamra.owners.release_block", { name: b.name }))}>
                      {t("Release")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {manage && (
            <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
              <h2 className="text-sm font-semibold">{t("Book a unit")}</h2>
              <p className="text-xs text-zinc-500">
                {t("A stay in one of your units, priced and checked like a booking at the desk.")}
              </p>
              <select className={inputCls} value={book.room} onChange={(e) => setBook({ ...book, room: e.target.value })}>
                <option value="">{t("Unit")}</option>
                {data.units.map((unit) => <option key={unit.room} value={unit.room}>{unit.room_number}</option>)}
              </select>
              <div className="flex gap-2">
                <input type="date" className={inputCls} value={book.from} onChange={(e) => setBook({ ...book, from: e.target.value })} />
                <input type="date" className={inputCls} value={book.to} onChange={(e) => setBook({ ...book, to: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <input className={inputCls} placeholder={t("Guest name")} value={book.guest}
                  onChange={(e) => setBook({ ...book, guest: e.target.value })} />
                <input className={inputCls + " max-w-24"} inputMode="numeric" aria-label={t("Adults")}
                  value={book.adults} onChange={(e) => setBook({ ...book, adults: e.target.value })} />
              </div>
              <button type="button" disabled={busy || !book.room || !book.guest.trim()}
                className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
                onClick={() => act(() => call("kamra.owners.book_unit", {
                  property, room: book.room, check_in_date: book.from, check_out_date: book.to,
                  guest_name: book.guest.trim(), adults: Number(book.adults) || 1,
                }))}>
                {t("Book")}
              </button>
            </div>
          )}
          {manage && (data.priceable_types ?? []).length > 0 && (
            <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
              <h2 className="text-sm font-semibold">{t("Set a rate")}</h2>
              <p className="text-xs text-zinc-500">
                {t("For a unit type whose units are all yours. The property's floor and ceiling still apply.")}
              </p>
              <select className={inputCls} value={price.type} onChange={(e) => setPrice({ ...price, type: e.target.value })}>
                <option value="">{t("Unit type")}</option>
                {(data.priceable_types ?? []).map((rt) => <option key={rt.room_type} value={rt.room_type}>{rt.name}</option>)}
              </select>
              <div className="flex gap-2">
                <input type="date" className={inputCls} value={price.from} onChange={(e) => setPrice({ ...price, from: e.target.value })} />
                <input type="date" className={inputCls} value={price.to} onChange={(e) => setPrice({ ...price, to: e.target.value })} />
                <input className={inputCls + " max-w-32"} inputMode="decimal" placeholder={t("Nightly rate")}
                  value={price.rate} onChange={(e) => setPrice({ ...price, rate: e.target.value })} />
              </div>
              <button type="button" disabled={busy || !price.type || !Number(price.rate)}
                className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50"
                onClick={() => act(() => call("kamra.owners.set_unit_rate", {
                  property, room_type: price.type, start_date: price.from, end_date: price.to,
                  rate: Number(price.rate),
                }))}>
                {t("Set rate")}
              </button>
            </div>
          )}
          <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold">{t("Statement")}</h2>
            <p className="text-xs text-zinc-500">
              {t("Room revenue per unit, minus commission and your costs that month. Guest names are not on this file.")}
            </p>
            <input type="month" className={inputCls} value={month} onChange={(e) => setMonth(e.target.value)} />
            <button type="button" disabled={busy || !month}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              onClick={() => act(async () => {
                setStatement(await call<Statement>("kamra.owners.my_statement", { property, month }))
              })}>
              {t("Show statement")}
            </button>
            {statement && (
              <div className="space-y-2 text-sm">
                <div>{statement.from_date} – {statement.to_date}</div>
                <div className="grid grid-cols-2 gap-2">
                  <Stat label={t("Room revenue")} value={String(statement.revenue)} />
                  <Stat label={t("Commission")} value={String(statement.commission)} />
                  <Stat label={t("Costs")} value={String(statement.costs)} />
                  <Stat label={t("Payout")} value={String(statement.payout)} />
                </div>
                <button type="button" className="underline" onClick={() => download(statement)}>
                  {t("Download statement")}
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  )
}
