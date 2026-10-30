import { useEffect, useRef, useState } from "react"
import { Download, FileText, Plus, Trash2, Upload, X } from "lucide-react"
import { Link } from "react-router-dom"

import {
  call,
  getBookingOptions,
  getCurrentProperty,
  type BookingOptions,
} from "../lib/api"
import { serverError } from "../lib/resource"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { Button } from "./ui/button"
import PhoneInput from "./PhoneInput"

/** New group booking (corporate, wedding, event), in the order the desk
 *  works a group: the group, its room blocks, the rooming list, then
 *  billing. One call to kamra.api.create_group_with_rooming_list books the
 *  named guests against the block; blocked rooms nobody is named for stay
 *  held until the cutoff and are picked up later from the group. */

interface BlockRow {
  room_type: string
  count: number
  /** the negotiated group rate per night, before tax ("" = normal price) */
  rate: string
  /** rooms per night when it differs night to night (null = `count` every night) */
  nightly: Record<string, number> | null
}
interface Guest {
  guest_name: string
  phone: string
  /** everyone else staying in the room, separated by ; */
  others: string
  /** the guest's own nights inside the group's dates ("" = the group's dates) */
  check_in_date?: string
  check_out_date?: string
}
interface Prices {
  rows: { room_type: string; room_type_name: string; rooms: number; room_nights: number;
          group_rate: boolean; rate: number; before_tax: number; tax: number; total: number }[]
  nights: number
  before_tax: number
  tax: number
  total: number
}
interface Result {
  group_booking: string
  status: string
  created: string[]
  skipped: { room_type: string; guest_name: string; reason: string }[]
  blocked: number
  held: number
  cutoff_date: string
}

const GROUP_TYPES = ["Corporate", "Wedding", "Event", "Tour", "Other"]
// what the main room pays: keys of folio.COMPANY_BILLING_DEFAULTS
const MASTER_PAYS: { value: string; label: string }[] = [
  { value: "Room only", label: "Room + tax" },
  { value: "Room and F&B (liquor to guest)", label: "Room and F&B (liquor to guest)" },
  { value: "Everything except liquor", label: "Everything except liquor" },
]

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const ymd = (x: Date) =>
  `${x.getFullYear()}-${`${x.getMonth() + 1}`.padStart(2, "0")}-${`${x.getDate()}`.padStart(2, "0")}`

const money = (n: number) =>
  `${cur()}${Number(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })}`

function addDay(d: string) {
  const x = new Date(`${d}T00:00:00`)
  x.setDate(x.getDate() + 1)
  return ymd(x)
}

/** Rows of a pasted Excel range or a CSV file: tab, comma or semicolon
 *  separated, quotes allowed. A first row naming a "name" column is a
 *  header and is dropped. */
export function parseGuestRows(text: string): string[][] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim())
  if (!lines.length) return []
  const sep = lines[0].includes("\t") ? "\t" : lines[0].includes(";") && !lines[0].includes(",") ? ";" : ","
  const rows = lines.map((line) => {
    const cells: string[] = []
    let cur = ""
    let quoted = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (quoted) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++ }
        else if (ch === '"') quoted = false
        else cur += ch
      } else if (ch === '"') quoted = true
      else if (ch === sep) { cells.push(cur.trim()); cur = "" }
      else cur += ch
    }
    cells.push(cur.trim())
    return cells
  })
  if (/name/i.test(rows[0][0] ?? "")) rows.shift()
  return rows.filter((r) => r[0])
}

export default function GroupBookingDialog(props: {
  onClose: () => void
  onDone: (group?: string) => void
}) {
  const { t } = useT()
  const today = ymd(new Date())
  const [options, setOptions] = useState<BookingOptions | null>(null)
  const [step, setStep] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [g, setG] = useState({
    group_name: "",
    group_type: "Wedding",
    check_in_date: today,
    check_out_date: addDay(today),
    payer: "main" as "main" | "company",
    company: "",
    guest_name: "",
    phone: "",
  })
  const [blocks, setBlocks] = useState<BlockRow[]>([])
  const [free, setFree] = useState<Record<string, number>>({})
  // rooming list: one slot per blocked room, keyed "<room type>#<n>"
  const [rooming, setRooming] = useState<Record<string, Guest>>({})
  const [masterKey, setMasterKey] = useState("")
  const [pays, setPays] = useState("Room only")
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteText, setPasteText] = useState("")
  const fileRef = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [prices, setPrices] = useState<Prices | null>(null)
  const [ownDates, setOwnDates] = useState(false)
  const [contract, setContract] = useState({ deposit_due: "", attrition_pct: "", quotation_only: false })
  // the less common choices (group rate, rooms per night, deposit, shortfall) stay folded away
  const [more, setMore] = useState(false)

  useEffect(() => {
    getBookingOptions()
      .then((o) => {
        setOptions(o)
        setBlocks([{ room_type: o.room_types[0]?.name ?? "", count: 1, rate: "", nightly: null }])
      })
      .catch((e) => setError(serverError(e)))
  }, [])

  // the group's nights, for rooms per night and each guest's own dates
  const nights: string[] = []
  for (let d = g.check_in_date; d && d < g.check_out_date && nights.length < 60; d = addDay(d)) nights.push(d)
  // rooms per night only mean something on a stay of two nights or more
  const perNight = (b: BlockRow) => (nights.length > 1 ? b.nightly : null)
  const peak = (b: BlockRow) => {
    const nightly = perNight(b)
    return nightly ? Math.max(0, ...nights.map((d) => nightly[d] ?? 0)) : b.count
  }
  const blockPayload = blocks
    .filter((b) => b.room_type && peak(b) > 0)
    .map((b) => ({
      room_type: b.room_type,
      rooms_blocked: peak(b),
      block_rate: Number(b.rate) || 0,
      nightly_counts: perNight(b) ? Object.fromEntries(nights.map((d) => [d, b.nightly?.[d] ?? 0])) : undefined,
    }))
  const blockKey = JSON.stringify([blockPayload, g.check_in_date, g.check_out_date])

  // what the block costs, priced by the server as the quotation will be
  useEffect(() => {
    if (!blockPayload.length || g.check_out_date <= g.check_in_date) { setPrices(null); return }
    const timer = setTimeout(() => {
      call<Prices>("kamra.api.group_price_preview", {
        property: getCurrentProperty(),
        check_in_date: g.check_in_date,
        check_out_date: g.check_out_date,
        blocks: blockPayload,
      }).then(setPrices).catch(() => setPrices(null))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blockKey])

  // how many rooms of each type are free on the group's dates
  const types = [...new Set(blocks.map((b) => b.room_type).filter(Boolean))].join("|")
  useEffect(() => {
    if (!types) return
    for (const rt of types.split("|")) {
      call<{ name: string }[]>("kamra.api.available_rooms", {
        property: getCurrentProperty(),
        room_type: rt,
        check_in_date: g.check_in_date,
        check_out_date: g.check_out_date,
      })
        .then((rs) => setFree((f) => ({ ...f, [rt]: rs.length })))
        .catch(() => {})
    }
  }, [types, g.check_in_date, g.check_out_date])

  const typeName = (rt: string) =>
    options?.room_types.find((x) => x.name === rt)?.room_type_name ?? rt
  const byMain = g.payer === "main"

  const blockedByType: Record<string, number> = {}
  for (const b of blocks) {
    if (b.room_type && peak(b) > 0) blockedByType[b.room_type] = (blockedByType[b.room_type] ?? 0) + peak(b)
  }
  const anyNightly = blocks.some((b) => perNight(b))
  // each guest's own nights: offered whenever rooms differ per night
  const datesOn = ownDates || anyNightly
  const total = Object.values(blockedByType).reduce((s, n) => s + n, 0)
  const slots = Object.entries(blockedByType).flatMap(([rt, n]) =>
    Array.from({ length: n }, (_, k) => ({ key: `${rt}#${k}`, room_type: rt })))
  const named = slots.filter((s) => rooming[s.key]?.guest_name.trim())
  // a type whose rooms differ per night is checked night by night on save
  const shortTypes = Object.entries(blockedByType).filter(
    ([rt, n]) => free[rt] !== undefined && n > free[rt]
      && !blocks.some((b) => b.room_type === rt && perNight(b)))

  const step1Ok =
    g.group_name.trim() &&
    g.guest_name.trim() &&
    g.check_in_date >= today &&
    g.check_out_date > g.check_in_date &&
    (byMain || g.company)
  const step2Ok = total > 0 && blocks.every((b) => b.room_type && peak(b) > 0) && !shortTypes.length
  const masterNamed = !!rooming[masterKey]?.guest_name.trim() && slots.some((s) => s.key === masterKey)
  const step3Ok = (!byMain || masterNamed) && !shortTypes.length
  const stepOk = [step1Ok, step2Ok, step3Ok][step - 1]

  // the pattern shown in the empty paste box, with the property's own room types
  const rtNames = options?.room_types.map((x) => x.room_type_name) ?? []
  const pastePattern = [
    t("Name, Phone, Room type, Other guests"),
    `Priya Sharma, +919876500000, ${rtNames[0] ?? "Standard"}, Ravi Sharma; Meera Sharma`,
    `Rahul Mehta, +919123456789, ${rtNames[1] ?? rtNames[0] ?? "Standard"}`,
    "Neha Gupta",
  ].join("\n")

  const setBlock = (i: number, patch: Partial<BlockRow>) =>
    setBlocks((bs) => bs.map((b, j) => (j === i ? { ...b, ...patch } : b)))
  const setGuest = (key: string, patch: Partial<Guest>) =>
    setRooming((r) => ({ ...r, [key]: { ...(r[key] ?? { guest_name: "", phone: "", others: "" }), ...patch } }))

  function next() {
    // the main guest fills the first room of the rooming list by default
    if (step === 2 && slots.length) {
      const first = slots[0].key
      const key = slots.some((s) => s.key === masterKey) ? masterKey : first
      setMasterKey(key)
      if (!rooming[key]?.guest_name.trim()) setGuest(key, { guest_name: g.guest_name.trim(), phone: g.phone })
    }
    setStep(step + 1)
  }

  /** Fill the rooming list from imported rows (Name, Phone, Room type). A
   *  row naming a room type goes to a room of that type. When every blocked
   *  room has a guest, the block grows by a room (while rooms are free). */
  function fillFrom(rows: string[][]) {
    const next = { ...rooming }
    const counts: Record<string, number> = { ...blockedByType }
    const grown: Record<string, number> = {}
    let placed = 0
    let left = 0
    for (const [name, phone = "", type = "", others = ""] of rows) {
      const want = type.trim().toLowerCase()
      const rt = want
        ? options?.room_types.find((x) => x.name.toLowerCase() === want || x.room_type_name.toLowerCase() === want)?.name
        : undefined
      let key: string | undefined
      for (const ty of rt ? [rt] : Object.keys(counts)) {
        for (let k = 0; k < (counts[ty] ?? 0) && !key; k++) {
          if (!next[`${ty}#${k}`]?.guest_name.trim()) key = `${ty}#${k}`
        }
      }
      if (!key) {
        const target = rt ?? Object.keys(counts)[0]
        if (!target || (counts[target] ?? 0) >= (free[target] ?? Infinity)) { left++; continue }
        counts[target] = (counts[target] ?? 0) + 1
        grown[target] = (grown[target] ?? 0) + 1
        key = `${target}#${counts[target] - 1}`
      }
      next[key] = { guest_name: name, phone, others }
      placed++
    }
    if (Object.keys(grown).length) {
      setBlocks((bs) => {
        const out = bs.map((b) => ({ ...b }))
        for (const [rt, n] of Object.entries(grown)) {
          const row = out.find((b) => b.room_type === rt)
          if (row) {
            row.count += n
            // a room added for a guest is held on every night
            if (row.nightly) row.nightly = Object.fromEntries(nights.map((d) => [d, (row.nightly?.[d] ?? 0) + n]))
          } else out.push({ room_type: rt, count: n, rate: "", nightly: null })
        }
        return out
      })
    }
    setRooming(next)
    const added = Object.values(grown).reduce((s, n) => s + n, 0)
    setNotice(
      [
        t("{n} guest(s) added.", { n: String(placed) }),
        added ? t("{n} room(s) added to the block.", { n: String(added) }) : "",
        left ? t("{m} did not fit - no more free rooms of that type on these dates.", { m: String(left) }) : "",
      ].filter(Boolean).join(" "),
    )
  }

  function onFile(file: File | undefined) {
    if (!file) return
    file.text().then((text) => fillFrom(parseGuestRows(text))).catch((e) => setError(String(e)))
    if (fileRef.current) fileRef.current.value = ""
  }

  async function create(quotationOnly = false) {
    setBusy(true)
    setError(null)
    const guests = named.map((s) => ({
      room_type: s.room_type,
      guest_name: rooming[s.key].guest_name.trim(),
      phone: rooming[s.key].phone || undefined,
      others: rooming[s.key].others?.trim() || undefined,
      check_in_date: (datesOn && rooming[s.key].check_in_date) || undefined,
      check_out_date: (datesOn && rooming[s.key].check_out_date) || undefined,
    }))
    const masterIndex = named.findIndex((s) => s.key === masterKey)
    try {
      const out = await call<Result>("kamra.api.create_group_with_rooming_list", {
        property: getCurrentProperty(),
        group_name: g.group_name.trim(),
        group_type: g.group_type,
        check_in_date: g.check_in_date,
        check_out_date: g.check_out_date,
        blocks: blockPayload,
        guests,
        deposit_due: Number(contract.deposit_due) || 0,
        attrition_pct: Number(contract.attrition_pct) || 0,
        quotation_only: quotationOnly ? 1 : 0,
        guest_name: g.guest_name.trim(),
        phone: g.phone || undefined,
        company: byMain ? undefined : g.company,
        ...(byMain ? { master_index: Math.max(0, masterIndex), master_pays: pays } : {}),
      })
      setResult(out)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const steps = [t("Group"), t("Rooms"), t("Guest names"), t("Price and confirm")]

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label={t("New group booking")}
      onKeyDown={(e) => e.key === "Escape" && props.onClose()}
    >
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={props.onClose} aria-hidden />
      <div className="absolute inset-y-0 right-0 flex h-full w-full flex-col bg-white shadow-2xl animate-sheet-in md:w-2/3 lg:w-1/2">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-zinc-200 px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold tracking-tight text-zinc-900">{t("New group booking")}</h2>
            <ol className="mt-1 flex flex-wrap gap-3 text-xs">
              {steps.map((s, i) => (
                <li key={s} className={i + 1 === step ? "font-semibold text-brand-700" : "text-zinc-400"}>
                  {i + 1}. {s}
                </li>
              ))}
            </ol>
          </div>
          <button onClick={props.onClose} aria-label={t("Close")} className="text-zinc-400 hover:text-zinc-700">
            <X className="size-5" />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
          )}

          {result ? (
            <div className="space-y-3 text-sm">
              <p className="text-base font-medium text-zinc-900">
                {result.status === "Open"
                  ? t("Quotation {group} saved for {b} room(s). No rooms are held until you confirm the block.", {
                      group: result.group_booking, b: String(result.blocked),
                    })
                  : t("Group {group} created: {b} room(s) blocked, {n} booked from the rooming list.", {
                      group: result.group_booking, b: String(result.blocked), n: String(result.created.length),
                    })}
              </p>
              <Link to={`/group-quote/${encodeURIComponent(result.group_booking)}`}
                className="inline-flex items-center gap-1.5 font-medium text-brand-700 hover:underline">
                <FileText className="size-4" />{t("Open the quotation to print or send")}
              </Link>
              {result.held > 0 && (
                <p className="text-zinc-600">
                  {t("{n} room(s) are held for the group until {date}. Name guests into them from the group's rooming list.", {
                    n: String(result.held), date: result.cutoff_date,
                  })}
                </p>
              )}
              {result.skipped.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-amber-700">
                  {result.skipped.map((s, i) => (
                    <li key={i}>{s.guest_name} ({typeName(s.room_type)}): {s.reason}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : step === 1 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Group name")}</span>
                <input className={inputCls} value={g.group_name} placeholder={t("e.g. Sharma Wedding")}
                  onChange={(e) => setG({ ...g, group_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Group type")}</span>
                <select className={inputCls} value={g.group_type} onChange={(e) => setG({ ...g, group_type: e.target.value })}>
                  {GROUP_TYPES.map((x) => <option key={x} value={x}>{t(x)}</option>)}
                </select>
              </label>
              <div />
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Arrival")}</span>
                <input type="date" className={inputCls} value={g.check_in_date} min={today}
                  onChange={(e) => setG({ ...g, check_in_date: e.target.value,
                    check_out_date: g.check_out_date > e.target.value ? g.check_out_date : addDay(e.target.value) })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Departure")}</span>
                <input type="date" className={inputCls} value={g.check_out_date} min={addDay(g.check_in_date)}
                  onChange={(e) => setG({ ...g, check_out_date: e.target.value })} />
              </label>
              <fieldset className="sm:col-span-2">
                <legend className="mb-1 text-sm font-medium text-zinc-600">{t("Who pays")}</legend>
                <div className="flex flex-wrap gap-4 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="radio" checked={byMain} onChange={() => setG({ ...g, payer: "main" })} />
                    {t("The main room's guest")}
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="radio" checked={!byMain} onChange={() => setG({ ...g, payer: "company" })} />
                    {t("A company")}
                  </label>
                </div>
              </fieldset>
              {!byMain && (
                <label className="block sm:col-span-2">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Company")}</span>
                  <select className={inputCls} value={g.company} onChange={(e) => setG({ ...g, company: e.target.value })}>
                    <option value="">{t("Choose a company…")}</option>
                    {options?.companies.map((c) => <option key={c.name} value={c.name}>{c.company_name}</option>)}
                  </select>
                </label>
              )}
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{byMain ? t("Main guest") : t("Contact name")}</span>
                <input className={inputCls} value={g.guest_name} onChange={(e) => setG({ ...g, guest_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Phone")}</span>
                <PhoneInput value={g.phone} onChange={(v) => setG({ ...g, phone: v })} />
              </label>
            </div>
          ) : step === 2 ? (
            <div className="space-y-3">
              <p className="text-sm text-zinc-600">
                {t("How many rooms does the group need? These rooms are kept for the group until the guests are named.")}
              </p>
              {blocks.map((b, i) => {
                const over = !perNight(b) && free[b.room_type] !== undefined && (blockedByType[b.room_type] ?? 0) > free[b.room_type]
                const price = prices?.rows.find((r) => r.room_type === b.room_type)
                return (
                  <div key={i} className="grid items-end gap-2 rounded-lg border border-zinc-200 p-3 sm:grid-cols-[2fr_6rem_8rem_auto]">
                    <label className="block">
                      <span className="mb-1 block text-xs text-zinc-500">{t("Room type")}</span>
                      <select className={inputCls} value={b.room_type} onChange={(e) => setBlock(i, { room_type: e.target.value })}>
                        {options?.room_types.map((rt) => <option key={rt.name} value={rt.name}>{rt.room_type_name}</option>)}
                      </select>
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs text-zinc-500">{t("Rooms")}</span>
                      <input type="number" min={1} className={inputCls} value={b.count} disabled={!!perNight(b)}
                        onChange={(e) => setBlock(i, { count: Math.max(0, Number(e.target.value) || 0) })} />
                    </label>
                    {more || b.rate ? (
                      <label className="block">
                        <span className="mb-1 block text-xs text-zinc-500">{t("Group rate / night")}</span>
                        <input type="number" min={0} className={inputCls} value={b.rate} placeholder={t("Normal price")}
                          onChange={(e) => setBlock(i, { rate: e.target.value })} />
                      </label>
                    ) : <span />}
                    <button aria-label={t("Remove room row")} disabled={blocks.length === 1}
                      onClick={() => setBlocks((bs) => bs.filter((_, j) => j !== i))}
                      className="pb-2 text-zinc-300 hover:text-rose-500 disabled:opacity-30">
                      <Trash2 className="size-4" />
                    </button>
                    <label className={`items-center gap-2 text-xs text-zinc-600 sm:col-span-4 ${nights.length > 1 && (more || b.nightly) ? "flex" : "hidden"}`}>
                      <input type="checkbox" checked={!!perNight(b)}
                        onChange={(e) => setBlock(i, {
                          nightly: e.target.checked ? Object.fromEntries(nights.map((d) => [d, b.count])) : null,
                          count: e.target.checked ? b.count : peak(b),
                        })} />
                      {t("Different number of rooms each night")}
                    </label>
                    {perNight(b) && (
                      <div className="flex flex-wrap gap-2 sm:col-span-4">
                        {nights.map((d) => (
                          <label key={d} className="block w-20">
                            <span className="block text-[11px] text-zinc-500">{d.slice(5)}</span>
                            <input type="number" min={0} className={`${inputCls} py-1`} value={b.nightly?.[d] ?? 0}
                              onChange={(e) => setBlock(i, { nightly: { ...b.nightly, [d]: Math.max(0, Number(e.target.value) || 0) } })} />
                          </label>
                        ))}
                      </div>
                    )}
                    <span className={`text-xs sm:col-span-4 ${over ? "text-rose-600" : "text-zinc-500"}`}>
                      {free[b.room_type] !== undefined && t("{n} free on these dates", { n: String(free[b.room_type]) })}
                      {price && ` · ${t("{rn} room-nights × {rate} + tax = {total}", {
                        rn: String(price.room_nights), rate: money(price.rate), total: money(price.total),
                      })}`}
                    </span>
                  </div>
                )
              })}
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" onClick={() =>
                  setBlocks((bs) => [...bs, { room_type: options?.room_types[0]?.name ?? "", count: 1, rate: "", nightly: null }])}>
                  <Plus className="size-4" />{t("Add room type")}
                </Button>
                <button type="button" className="text-sm font-medium text-brand-700 hover:underline" onClick={() => setMore((m) => !m)}>
                  {more ? t("Fewer options")
                    : nights.length > 1 ? t("More options: group rate, different rooms per night")
                      : t("More options: group rate")}
                </button>
              </div>
              <div className="rounded-lg bg-zinc-50 px-4 py-2 text-sm text-zinc-600">
                {Object.entries(blockedByType).map(([rt, n]) => `${typeName(rt)} – ${n}`).join(" · ")}
                {" · "}{t("{n} room(s)", { n: String(total) })}
                {prices && (
                  <span className="block font-medium text-zinc-900">
                    {t("Rooms total {v0} (before tax {v1} + tax {v2})", {
                      v0: money(prices.total), v1: money(prices.before_tax), v2: money(prices.tax),
                    })}
                  </span>
                )}
              </div>
            </div>
          ) : step === 3 ? (
            <div className="space-y-3 text-sm">
              <p className="text-zinc-600">
                {t("Name the guest for each room, one by one or from Excel. Rooms left empty stay held for the group and can be named later.")}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setPasteOpen((o) => !o)}>{t("Paste from Excel")}</Button>
                <Button variant="outline" onClick={() => fileRef.current?.click()}>
                  <Upload className="size-4" />{t("Upload CSV")}
                </Button>
                <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden"
                  onChange={(e) => onFile(e.target.files?.[0])} />
                <a
                  href={`/api/method/kamra.api.rooming_list_template?property=${encodeURIComponent(getCurrentProperty() ?? "")}`}
                  download
                  className="inline-flex items-center gap-1.5 self-center px-2 text-sm font-medium text-brand-700 hover:underline"
                >
                  <Download className="size-4" />{t("Download template")}
                </a>
              </div>
              {pasteOpen && (
                <div className="space-y-2 rounded-lg bg-zinc-50 p-3">
                  <p className="text-xs text-zinc-500">
                    {t("Copy the Name, Phone, Room type and Other guests columns from Excel (only Name is required) and paste them here, one room per line. Separate other guests with ;")}
                  </p>
                  <textarea className={`${inputCls} h-32 font-mono text-xs`} value={pasteText}
                    placeholder={pastePattern}
                    onChange={(e) => setPasteText(e.target.value)} />
                  <div className="flex gap-2">
                    <Button disabled={!pasteText.trim()} onClick={() => {
                      fillFrom(parseGuestRows(pasteText))
                      setPasteText("")
                      setPasteOpen(false)
                    }}>{t("Fill names")}</Button>
                    <Button variant="outline" onClick={() => setPasteOpen(false)}>{t("Close")}</Button>
                  </div>
                </div>
              )}
              {notice && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{notice}</div>
              )}
              <label className="flex items-center gap-2 text-xs text-zinc-600">
                <input type="checkbox" checked={datesOn} disabled={anyNightly}
                  onChange={(e) => setOwnDates(e.target.checked)} />
                {t("Some guests stay fewer nights (set their own dates)")}
              </label>
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="py-1 pr-2 font-medium">#</th>
                    <th className="py-1 pr-2 font-medium">{t("Room type")}</th>
                    <th className="py-1 pr-2 font-medium">{t("Guest")}</th>
                    <th className="py-1 pr-2 font-medium">{t("Phone")}</th>
                    {byMain && <th className="py-1 font-medium">{t("Main room")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {slots.map((s, i) => (
                    <tr key={s.key} className="border-t border-zinc-100">
                      <td className="py-1 pr-2 text-zinc-400">{i + 1}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">{typeName(s.room_type)}</td>
                      <td className="py-1 pr-2">
                        <input className={`${inputCls} py-1`} aria-label={t("Guest for room {n}", { n: String(i + 1) })}
                          placeholder={t("Empty = name later")}
                          value={rooming[s.key]?.guest_name ?? ""}
                          onChange={(e) => setGuest(s.key, { guest_name: e.target.value })} />
                        <input className={`${inputCls} mt-1 py-1 text-xs`} aria-label={t("Others staying in room {n}", { n: String(i + 1) })}
                          placeholder={t("Others staying (optional), e.g. Ravi; Meera")}
                          value={rooming[s.key]?.others ?? ""}
                          onChange={(e) => setGuest(s.key, { others: e.target.value })} />
                        {datesOn && (
                          <div className="mt-1 flex items-center gap-1 text-xs">
                            <input type="date" className={`${inputCls} py-1 text-xs`} aria-label={t("Arrival for room {n}", { n: String(i + 1) })}
                              min={g.check_in_date} max={nights[nights.length - 1]}
                              value={rooming[s.key]?.check_in_date || g.check_in_date}
                              onChange={(e) => setGuest(s.key, { check_in_date: e.target.value })} />
                            →
                            <input type="date" className={`${inputCls} py-1 text-xs`} aria-label={t("Departure for room {n}", { n: String(i + 1) })}
                              min={addDay(rooming[s.key]?.check_in_date || g.check_in_date)} max={g.check_out_date}
                              value={rooming[s.key]?.check_out_date || g.check_out_date}
                              onChange={(e) => setGuest(s.key, { check_out_date: e.target.value })} />
                          </div>
                        )}
                      </td>
                      <td className="py-1 pr-2">
                        <input className={`${inputCls} w-36 py-1`} aria-label={t("Phone for room {n}", { n: String(i + 1) })}
                          value={rooming[s.key]?.phone ?? ""}
                          onChange={(e) => setGuest(s.key, { phone: e.target.value })} />
                      </td>
                      {byMain && (
                        <td className="py-1 text-center">
                          <input type="radio" aria-label={t("Main room")} checked={masterKey === s.key}
                            onChange={() => setMasterKey(s.key)} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-zinc-500">
                {t("{n} of {total} room(s) named.", { n: String(named.length), total: String(total) })}
                {byMain && !masterNamed && ` ${t("Name the main room's guest to continue.")}`}
                {named.length === total && ` ${t("Every room has a guest - paste more names to add rooms.")}`}
                {shortTypes.map(([rt, n]) => (
                  <span key={rt} className="block text-rose-600">
                    {t("{type}: {n} rooms needed, only {f} free on these dates.", { type: typeName(rt), n: String(n), f: String(free[rt]) })}
                  </span>
                ))}
              </p>
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              {prices && (
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-zinc-500">
                      <th className="py-1 pr-2 font-medium">{t("Room type")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{t("Room-nights")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{t("Rate / night")}</th>
                      <th className="py-1 text-right font-medium">{t("Amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prices.rows.map((r) => (
                      <tr key={r.room_type} className="border-t border-zinc-100">
                        <td className="py-1 pr-2">{r.room_type_name}{r.group_rate && <span className="ml-1 text-xs text-brand-700">{t("group rate")}</span>}</td>
                        <td className="py-1 pr-2 text-right">{r.room_nights}</td>
                        <td className="py-1 pr-2 text-right">{money(r.rate)}</td>
                        <td className="py-1 text-right">{money(r.total)}</td>
                      </tr>
                    ))}
                    <tr className="border-t border-zinc-200 font-semibold">
                      <td colSpan={3} className="py-1 pr-2 text-right">{t("Rooms total (with tax)")}</td>
                      <td className="py-1 text-right">{money(prices.total)}</td>
                    </tr>
                  </tbody>
                </table>
              )}
              <button type="button" className="text-sm font-medium text-brand-700 hover:underline" onClick={() => setMore((m) => !m)}>
                {more ? t("Fewer options") : t("More options: deposit, rooms they can give back free")}
              </button>
              <div className={`gap-3 sm:grid-cols-2 ${more ? "grid" : "hidden"}`}>
                <label className="block">
                  <span className="mb-1 block font-medium text-zinc-600">{t("Deposit to ask for")}</span>
                  <input type="number" min={0} className={inputCls} value={contract.deposit_due}
                    placeholder={prices ? t("e.g. 25% = {v0}", { v0: money(Math.round(prices.total * 0.25)) }) : ""}
                    onChange={(e) => setContract({ ...contract, deposit_due: e.target.value })} />
                </label>
                <label className="block">
                  <span className="mb-1 block font-medium text-zinc-600">{t("Rooms they can give back free (%)")}</span>
                  <input type="number" min={0} max={100} className={inputCls} value={contract.attrition_pct}
                    placeholder={t("e.g. 10")}
                    onChange={(e) => setContract({ ...contract, attrition_pct: e.target.value })} />
                  <span className="mt-1 block text-xs text-zinc-500">{t("Kamra warns you before the hold date if the group has used fewer rooms than agreed.")}</span>
                </label>
              </div>
              <p className="rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
                {t("Not sure yet? Save as quotation - nothing is kept or booked, and you can print it for the client. Book group keeps the rooms and books the named guests now.")}
              </p>
              {byMain ? (
                <label className="block">
                  <span className="mb-1 block font-medium text-zinc-600">{t("The main room pays")}</span>
                  <select className={inputCls} value={pays} onChange={(e) => setPays(e.target.value)}>
                    {MASTER_PAYS.map((m) => <option key={m.value} value={m.value}>{t(m.label)}</option>)}
                  </select>
                  <span className="mt-1 block text-xs text-zinc-500">{t("For every room of the group, on one group bill. Each guest pays their own extras; liquor always stays with the guest.")}</span>
                </label>
              ) : (
                <p className="text-zinc-600">{t("The company's billing rules decide what it pays, on one group bill.")}</p>
              )}
              <div className="space-y-1 rounded-lg bg-zinc-50 px-4 py-3">
                <div className="font-medium">{g.group_name} · {t(g.group_type)}</div>
                <div className="text-zinc-500">{g.check_in_date} → {g.check_out_date}</div>
                {Object.entries(blockedByType).map(([rt, n]) => {
                  const k = named.filter((s) => s.room_type === rt).length
                  return (
                    <div key={rt} className="text-zinc-600">
                      {typeName(rt)}: {t("{n} blocked · {k} booked now · {h} held", { n: String(n), k: String(k), h: String(n - k) })}
                    </div>
                  )
                })}
                {byMain && masterNamed && (
                  <div className="text-zinc-600">{t("Main room")}: {rooming[masterKey].guest_name}</div>
                )}
              </div>
            </div>
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-zinc-200 px-6 py-3">
          {result ? (
            <>
              <Button variant="outline" onClick={() => props.onDone()}>{t("Done")}</Button>
              <Button onClick={() => props.onDone(result.group_booking)}>{t("Open group")}</Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => (step === 1 ? props.onClose() : setStep(step - 1))}>
                {step === 1 ? t("Cancel") : t("Back")}
              </Button>
              {step < 4 ? (
                <Button disabled={!stepOk} onClick={next}>{t("Next")}</Button>
              ) : (
                <div className="flex gap-2">
                  <Button variant="outline" disabled={busy} onClick={() => create(true)}>{t("Save as quotation")}</Button>
                  <Button disabled={busy} onClick={() => create(false)}>{t("Book group")}</Button>
                </div>
              )}
            </>
          )}
        </footer>
      </div>
    </div>
  )
}
