/** Unit owners (#639). Hotel Admin links an owner to units and logins.
 *  The owner signs in and sees only those units: a calendar, occupancy,
 *  bookings, room revenue and a monthly statement. Manage can hold one
 *  of their own units. Guest name and phone stay hidden unless the admin
 *  turns Show guest contact on. */

import { useCallback, useEffect, useState } from "react"
import { call, getCurrentProperty, serverError } from "../lib/api"
import { useAuth } from "../lib/auth"
import { useT } from "../lib/i18n"

const ADMIN = ["Hotel Admin", "System Manager", "Administrator"]

interface OwnerRow {
  name: string
  owner_name: string
  access: string
  show_guest_contact: number
  commission_percent: number
  units: string[]
  users: string[]
}
interface RoomRow { name: string; room_number: string }
interface Desk {
  owners: OwnerRow[]
  rooms: RoomRow[]
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
  units: { room: string; room_number: string; occupancy_status: string }[]
  bookings: Booking[]
  blocks: Hold[]
}
interface Statement {
  from_date: string
  to_date: string
  room_nights: number
  revenue: number
  commission: number
  costs: number
  payout: number
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
      {tab === "desk" && admin ? <DeskPanel /> : <PortalPanel />}
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
  const [users, setUsers] = useState("")

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
        users: users.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean),
      })
      setName("")
      setOwnerName("")
      setUsers("")
      setRooms([])
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
          {t("A new email is created as a login. Set the password in Staff & Access. Manage can hold their own units. Read only cannot.")}
        </p>
        <div className="flex flex-wrap gap-2">
          {(desk?.rooms ?? []).map((r) => (
            <label key={r.name} className="flex items-center gap-1 rounded-full border border-zinc-200 px-2 py-1 text-sm">
              <input type="checkbox" checked={rooms.includes(r.name)}
                onChange={(e) => setRooms(e.target.checked
                  ? [...rooms, r.name]
                  : rooms.filter((x) => x !== r.name))} />
              {r.room_number}
            </label>
          ))}
        </div>
        <textarea className={inputCls} rows={2} placeholder={t("Login emails, one per line")}
          value={users} onChange={(e) => setUsers(e.target.value)} />
        <button type="button" disabled={busy || !ownerName}
          onClick={save}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          {name ? t("Save owner") : t("Add owner")}
        </button>
      </div>
      <ul className="space-y-2">
        {(desk?.owners ?? []).map((row) => (
          <li key={row.name} className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white p-3 text-sm">
            <div>
              <div className="font-medium">{row.owner_name}</div>
              <div className="text-zinc-500">
                {t(row.access)} · {row.commission_percent}% · {row.units.length} {t("units")} · {row.users.join(", ")}
                {row.show_guest_contact ? ` · ${t("guest contact on")}` : ""}
              </div>
            </div>
            <button type="button" className="text-sm text-zinc-700 underline" onClick={() => edit(row)}>
              {t("Edit")}
            </button>
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
          <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold">{t("Statement")}</h2>
            <p className="text-xs text-zinc-500">
              {t("Room revenue minus commission. Costs are not itemised yet, and guest names are not on this file.")}
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
