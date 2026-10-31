import { useCallback, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Star, Trash2 } from "lucide-react"

import { call } from "../lib/api"
import { useRealtime } from "../lib/realtime"
import { serverError, type Row } from "../lib/resource"
import LinkedRecords from "./LinkedRecords"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"
import { useCashierAuth } from "../lib/cashierAuth"
import CheckInDialog from "./CheckInDialog"
import CheckOutDialog from "./CheckOutDialog"

/** One group, in the order the desk works it. A "What to do next" box
 *  follows the group's stage (quotation, before arrival, arrival day, in
 *  house, settle the bill); below it three tabs: Guests (names, check-in,
 *  check-out), Rooms (the rooms kept for the group) and Bill (who pays,
 *  deposit, the group bill). */

interface PickupRow {
  room_type: string
  room_type_name: string
  rooms_blocked: number
  block_rate: number
  /** rooms per night when it differs night to night ({} otherwise) */
  nightly_counts: Record<string, number>
  picked_up: number
  remaining: number
}
interface Guest {
  name: string
  guest_name: string
  phone: string | null
  room_type: string
  room_type_name: string
  room: string | null
  room_number: string | null
  status: string
  check_in_date: string
  check_out_date: string
  pays_own_charges: 0 | 1
  is_master: boolean
  /** what the guest still owes on their own bill */
  own_balance: number
  amount: number
}
interface Detail {
  business_date?: string
  group: {
    name: string
    group_name: string
    company: string | null
    status: string
    check_in_date: string
    check_out_date: string
    cutoff_date: string | null
    notes: string | null
    group_type: string | null
    master_reservation: string | null
    master_pays: string | null
    in_house: number
    attrition_pct: number
    deposit_due: number
  }
  pickup: PickupRow[]
  money: { block_value: number; booked: number; deposits: number; paid: number; deposit_due: number; due: number }
  attrition: {
    blocked_room_nights: number
    picked_room_nights: number
    pickup_pct: number
    allowed_pct: number
    shortfall_room_nights: number
    fee_estimate: number
    days_to_cutoff: number
    warn: boolean
  }
  room_types: { name: string; room_type_name: string }[]
  /** may this user set the billed group rate (Revenue Manager / Hotel Admin) */
  can_set_rate: boolean
  rooming_list: Guest[]
  event: {
    name: string
    venue: string
    event_type: string
    event_date: string
    status: string
    attendees: number
    quoted_amount: number
  } | null
  master_folio: string | null
  master_folio_status: string | null
  master_folio_balance: number
}

interface BlockDraft {
  room_type: string
  rooms_blocked: string
  block_rate: string
}

/** one room's outcome from a group action (kamra.api.group_* / group_checkout) */
interface RoomResult {
  reservation: string
  error?: string
  skipped?: string
  unchanged?: number
}

type Tab = "guests" | "rooms" | "bill"
type Stage = "quote" | "before" | "arrival" | "inhouse" | "settle" | "done" | "cancelled"

/** "6 done, 2 skipped: No room assigned; …" */
function summarize(results: RoomResult[], doneLabel: string): string {
  const failed = results.filter((r) => r.error || r.skipped)
  const done = results.length - failed.length - results.filter((r) => r.unchanged).length
  const parts = [translate("{v0} {v1}", { v0: String(done), v1: doneLabel })]
  if (failed.length)
    parts.push(
      translate("{v0} skipped: {v1}", {
        v0: String(failed.length),
        v1: Array.from(
          new Set(failed.map((r) => translate(r.skipped ?? r.error ?? ""))),
        ).join("; "),
      }),
    )
  return parts.join(", ")
}

const short = (rt: string) => rt.split("-").pop() ?? rt
const inr = (n: number) =>
  `${cur()}` + Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })
const todayLocal = () => {
  const x = new Date()
  return `${x.getFullYear()}-${`${x.getMonth() + 1}`.padStart(2, "0")}-${`${x.getDate()}`.padStart(2, "0")}`
}
const daysBetween = (a: string, b: string) =>
  Math.round((new Date(`${b}T00:00:00`).getTime() - new Date(`${a}T00:00:00`).getTime()) / 86400000)

const STATUS_TONE: Record<string, "green" | "amber" | "zinc"> = {
  "Checked In": "green",
  Confirmed: "amber",
}
const inputSm = "rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
const sectionTitle = "mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500"

export default function GroupControl({
  row,
  reload,
}: {
  row: Row
  reload: () => void
}) {
  useUILanguage()
  const name = String(row.name)
  const [d, setD] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<Tab | null>(null)
  const [blocks, setBlocks] = useState<BlockDraft[]>([])
  const [cutoff, setCutoff] = useState("")
  const [terms, setTerms] = useState({ attrition_pct: "", deposit_due: "" })
  const [deposit, setDeposit] = useState<{ amount: string; mode: string } | null>(null)
  const [pick, setPick] = useState({ room_type: "", guest_name: "", phone: "" })
  const [settle, setSettle] = useState<{ mode: string; amount: string; cityLedger: boolean } | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  // rooms checked in by the group button that still have steps to finish
  const [unfinished, setUnfinished] = useState<Set<string>>(new Set())
  const loc = useLocale()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()
  const [names, setNames] = useState<Record<string, { guest_name: string; phone: string }>>({})
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteText, setPasteText] = useState("")
  const [datesOpen, setDatesOpen] = useState(false)
  const [newDates, setNewDates] = useState({ check_in_date: "", check_out_date: "" })
  const [notice, setNotice] = useState<string | null>(null)
  const namesDirty = useRef(false)

  const load = useCallback(() => {
    call<Detail>("kamra.api.group_detail", { group_booking: name })
      .then((r) => {
        setD(r)
        // a live reload keeps names the desk is still typing
        const fresh = Object.fromEntries(
          r.rooming_list.map((x) => [
            x.name,
            { guest_name: x.guest_name ?? "", phone: x.phone ?? "" },
          ]),
        )
        setNames((prev) => (namesDirty.current ? { ...fresh, ...prev } : fresh))
        setBlocks(
          r.pickup.map((p) => ({
            room_type: p.room_type,
            rooms_blocked: String(p.rooms_blocked),
            block_rate: p.block_rate ? String(p.block_rate) : "",
          })),
        )
        setCutoff(r.group.cutoff_date ?? "")
        setTerms({
          attrition_pct: r.group.attrition_pct ? String(r.group.attrition_pct) : "",
          deposit_due: r.group.deposit_due ? String(r.group.deposit_due) : "",
        })
        setPick((pk) => ({ ...pk, room_type: r.pickup.find((p) => p.remaining > 0)?.room_type ?? r.pickup[0]?.room_type ?? "" }))
      })
      .catch((e) => setError(serverError(e)))
  }, [name])
  useEffect(load, [load])
  useRealtime(load)

  async function act(fn: () => Promise<unknown>, money = false) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      if (money && pinStatus?.required) await ensureUnlocked()
      await fn()
      load()
      reload()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const saveBlocks = (status?: string) =>
    act(async () => {
      await call("kamra.api.save_group_blocks", {
        group_booking: name,
        blocks: blocks
          .filter((b) => b.room_type && Number(b.rooms_blocked) > 0)
          .map((b) => ({
            room_type: b.room_type,
            rooms_blocked: Number(b.rooms_blocked),
            block_rate: Number(b.block_rate) || 0,
          })),
        cutoff_date: cutoff || null,
        status: status ?? null,
        attrition_pct: Number(terms.attrition_pct) || 0,
        deposit_due: Number(terms.deposit_due) || 0,
      })
      setNotice(status === "Confirmed" ? translate("Booking confirmed - the rooms are now kept for the group.") : translate("Saved."))
    })

  /** an advance for the whole group, paid into the group bill */
  const takeDeposit = (amount: number, mode: string) =>
    act(async () => {
      const { folio } = await call<{ folio: string }>("kamra.api.group_master_folio", { group_booking: name })
      await call("kamra.api.add_folio_payment", { folio, mode, amount, kind: "Advance" })
      setDeposit(null)
      setNotice(translate("Deposit of {v0} received on the group bill.", { v0: inr(amount) }))
    }, true)

  if (!d)
    return (
      <p className="py-8 text-center text-sm text-zinc-400">
        {translate(error) ?? translate("Loading group…")}
      </p>
    )

  const g = d.group
  const list = d.rooming_list
  const active = (r: Guest) => r.status === "Confirmed" || r.status === "Checked In"
  // every room with a guest, including those who have already checked out
  const namedCount = list.filter((r) => active(r) || r.status === "Checked Out").length
  // a group action works on the ticked rooms, or on every room
  const targets = selected.size ? list.filter((r) => selected.has(r.name)) : list
  const countOf = (...statuses: string[]) => targets.filter((r) => statuses.includes(r.status)).length
  const reservations = selected.size ? [...selected] : undefined
  const changedNames = list.filter((r) => {
    const n = names[r.name]
    return (
      active(r) && n && n.guest_name.trim() &&
      (n.guest_name.trim() !== r.guest_name || n.phone.trim() !== (r.phone ?? ""))
    )
  })
  const ciCount = countOf("Confirmed")
  const noRoomCount = targets.filter((r) => r.status === "Confirmed" && !r.room).length
  const coCount = countOf("Checked In")
  const amendCount = countOf("Confirmed", "Checked In")
  const toArrive = list.filter((r) => r.status === "Confirmed").length
  const inHouse = list.filter((r) => r.status === "Checked In").length
  const kept = d.pickup.reduce((s, p) => s + p.rooms_blocked, 0)
  const stillFree = d.pickup.reduce((s, p) => s + p.remaining, 0)
  const guestsOwe = list.filter((r) => r.own_balance > 0.5)
  const today = d.business_date ?? todayLocal()
  const groupBillDue = d.master_folio_status === "Open" ? d.master_folio_balance : 0

  const stage: Stage =
    g.status === "Cancelled" ? "cancelled"
      : g.status === "Open" ? "quote"
        : toArrive > 0 && today >= g.check_in_date ? "arrival"
          : inHouse > 0 ? "inhouse"
            : toArrive > 0 || today < g.check_in_date ? "before"
              : groupBillDue > 0.5 ? "settle" : "done"
  const shownTab: Tab = tab ?? (stage === "settle" || stage === "done" ? "bill" : stage === "quote" ? "rooms" : "guests")
  const main = list.find((r) => r.is_master)

  function groupAction(method: string, args: Record<string, unknown>, question: string, doneLabel: string) {
    if (!confirm(question)) return
    act(async () => {
      const out = await call<{ results: RoomResult[] }>(method, { ...args, reservations })
      setSelected(new Set())
      setNotice(summarize(out.results, doneLabel))
    })
  }
  const checkInAll = () => {
    if (!confirm(translate("Check in {v0} room(s)? Rooms with no room number get a free one. Add each guest's ID afterwards from their check-in.", { v0: String(ciCount) }))) return
    act(async () => {
      const out = await call<{ results: RoomResult[]; checked_in: { reservation: string; pending: string[] }[] }>(
        "kamra.api.group_check_in", { group_booking: name, reservations })
      setSelected(new Set())
      setUnfinished(new Set(out.checked_in.filter((x) => x.pending.length).map((x) => x.reservation)))
      setNotice(summarize(out.results, translate("checked in")))
    })
  }
  const giveRooms = () =>
    groupAction(
      "kamra.api.group_assign_rooms", { group_booking: name },
      translate("Give {v0} room(s) a free room number?", { v0: String(noRoomCount) }),
      translate("got a room number"),
    )
  const openSettle = () => {
    setTab("bill")
    setSettle({ mode: loc.payment_modes[0] ?? "Cash", amount: String(Math.round(groupBillDue) || ""), cityLedger: !!g.company })
  }
  const openDeposit = () => {
    setTab("bill")
    setDeposit({
      amount: String(Math.max(0, d.money.deposit_due - d.money.deposits) || ""),
      mode: loc.payment_modes[0] ?? "Cash",
    })
  }

  function saveNames() {
    act(async () => {
      const out = await call<{ results: RoomResult[] }>("kamra.api.set_rooming_names", {
        group_booking: name,
        names: changedNames.map((r) => ({
          reservation: r.name,
          guest_name: names[r.name].guest_name.trim(),
          phone: names[r.name].phone.trim(),
        })),
      })
      namesDirty.current = false
      setNotice(summarize(out.results, translate("named")))
    })
  }

  function setName(res: string, field: "guest_name" | "phone", value: string) {
    namesDirty.current = true
    setNames((ns) => ({ ...ns, [res]: { ...(ns[res] ?? { guest_name: "", phone: "" }), [field]: value } }))
  }

  /** Paste from Excel: Name, Phone (tab or comma), one guest per line,
   *  filled into the (ticked, else all) rooms in order. */
  function applyPaste() {
    let lines = pasteText.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
    if (lines[0] && /^(guest\s*)?name\b/i.test(lines[0])) lines = lines.slice(1)
    const rooms = targets.filter(active)
    namesDirty.current = true
    setNames((ns) => {
      const next = { ...ns }
      rooms.forEach((r, i) => {
        if (!lines[i]) return
        const [guest, phone] = lines[i].split(/\t|,/)
        next[r.name] = { guest_name: (guest ?? "").trim(), phone: (phone ?? next[r.name]?.phone ?? "").trim() }
      })
      return next
    })
    setPasteOpen(false)
    setPasteText("")
    setNotice(
      lines.length > rooms.length
        ? translate("{v0} names for {v1} rooms - the extra names were left out. Add them with \"Add a guest\" below.", {
            v0: String(lines.length), v1: String(rooms.length),
          })
        : translate("Names filled in - check them, then press Save names."),
    )
  }

  /* ------------------------------ next step ------------------------------ */
  const nextStep = (() => {
    switch (stage) {
      case "quote":
        return {
          tone: "amber",
          text: translate("This is a quotation - no rooms are kept yet. Send it to the client; when they agree, confirm it."),
          actions: (
            <>
              <Link to={`/group-quote/${encodeURIComponent(name)}`} className="inline-flex items-center rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-zinc-50">
                {translate("Print quotation")}
              </Link>
              <Button disabled={busy} onClick={() => saveBlocks("Confirmed")}>{translate("Confirm booking")}</Button>
            </>
          ),
        }
      case "before": {
        const days = daysBetween(today, g.check_in_date)
        return {
          tone: "brand",
          text: [
            days > 0 ? translate("Arrives in {v0} day(s).", { v0: String(days) }) : translate("Arrives today."),
            translate("{v0} of {v1} rooms have a guest name.", { v0: String(namedCount), v1: String(kept) }),
            stillFree > 0 && g.cutoff_date
              ? translate("{v0} room(s) are kept free for the group until {v1}.", { v0: String(stillFree), v1: g.cutoff_date })
              : "",
          ].filter(Boolean).join(" "),
          actions: (
            <>
              {stillFree > 0 && <Button variant="outline" onClick={() => setTab("guests")}>{translate("Add guest names")}</Button>}
              {d.money.deposits < d.money.deposit_due && (
                <Button variant="outline" onClick={openDeposit}>{translate("Take deposit")}</Button>
              )}
              <Link to={`/group-quote/${encodeURIComponent(name)}`} className="inline-flex items-center rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-zinc-50">
                {translate("Print quotation")}
              </Link>
            </>
          ),
        }
      }
      case "arrival":
        return {
          tone: "brand",
          text: translate("{v0} room(s) arriving - check them in.", { v0: String(toArrive) }),
          actions: (
            <>
              <Button disabled={busy} onClick={checkInAll}>{translate("Check in all ({v0})", { v0: String(toArrive) })}</Button>
              <Button variant="outline" onClick={() => setTab("guests")}>{translate("Check in one by one")}</Button>
            </>
          ),
        }
      case "inhouse":
        return {
          tone: "brand",
          text: [
            translate("{v0} room(s) in house.", { v0: String(inHouse) }),
            today >= g.check_out_date ? translate("Departure today: each guest pays their own extras at check-out.") : "",
            guestsOwe.length ? translate("{v0} guest(s) owe on their own bill.", { v0: String(guestsOwe.length) }) : "",
          ].filter(Boolean).join(" "),
          actions: <Button variant="outline" onClick={() => setTab("guests")}>{translate("Check out guests")}</Button>,
        }
      case "settle":
        return {
          tone: "amber",
          text: translate("Everyone has checked out. The group bill still has {v0} to settle.", { v0: inr(groupBillDue) }),
          actions: <Button disabled={busy} onClick={openSettle}>{translate("Settle group bill")}</Button>,
        }
      case "done":
        return { tone: "green", text: translate("All done - every guest has checked out and the group bill is settled."), actions: null }
      default:
        return { tone: "zinc", text: translate("This group is cancelled."), actions: null }
    }
  })()
  const toneCls: Record<string, string> = {
    amber: "border-amber-300 bg-amber-50 text-amber-900",
    brand: "border-brand-200 bg-brand-50 text-brand-900",
    green: "border-emerald-200 bg-emerald-50 text-emerald-900",
    zinc: "border-zinc-200 bg-zinc-50 text-zinc-700",
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "guests", label: translate("Guests ({v0})", { v0: String(namedCount) }) },
    { key: "rooms", label: translate("Rooms") },
    { key: "bill", label: translate("Bill") },
  ]

  return (
    <div className="space-y-4">
      {/* header */}
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold">{g.group_name}</div>
          <div className="text-sm text-zinc-500">
            {g.check_in_date} → {g.check_out_date}
            {" · "}{translate("{v0} night(s)", { v0: String(daysBetween(g.check_in_date, g.check_out_date)) })}
            {g.company && <> · {g.company}</>}
          </div>
        </div>
        <Badge tone={g.status === "Confirmed" ? "green" : g.status === "Open" ? "amber" : "zinc"}>
          {translate(g.status === "Open" ? "Quotation" : g.status)}
        </Badge>
      </div>

      {/* what to do next */}
      <div className={`space-y-2 rounded-lg border px-4 py-3 text-sm ${toneCls[nextStep.tone]}`}>
        <div><span className="font-semibold">{translate("What to do next")}: </span>{nextStep.text}</div>
        {nextStep.actions && <div className="flex flex-wrap gap-2">{nextStep.actions}</div>}
      </div>

      {/* at a glance */}
      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div className="rounded-lg border border-zinc-200 px-3 py-2">
          <div className="text-xs text-zinc-500">{translate("Rooms")}</div>
          <div className="font-semibold">{translate("{v0} named of {v1}", { v0: String(namedCount), v1: String(kept) })}</div>
        </div>
        <div className="rounded-lg border border-zinc-200 px-3 py-2">
          <div className="text-xs text-zinc-500">{translate("Room charges (with tax)")}</div>
          <div className="font-semibold">{inr(Math.max(d.money.block_value, d.money.booked))}</div>
        </div>
        <div className="rounded-lg border border-zinc-200 px-3 py-2">
          <div className="text-xs text-zinc-500">{translate("Paid so far")}</div>
          <div className="font-semibold">{inr(d.money.paid)}</div>
        </div>
        <div className="rounded-lg border border-zinc-200 px-3 py-2">
          <div className="text-xs text-zinc-500">{translate("Still to pay")}</div>
          <div className="font-semibold text-brand-700">{inr(d.money.due)}</div>
        </div>
      </div>

      {d.attrition.warn && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {d.attrition.days_to_cutoff >= 0
            ? translate("Only {v0}% of the kept rooms have guests, and the rooms are released in {v1} day(s).", {
                v0: String(d.attrition.pickup_pct), v1: String(d.attrition.days_to_cutoff),
              })
            : translate("The hold date has passed with {v0}% of the kept rooms used.", { v0: String(d.attrition.pickup_pct) })}
          {d.attrition.fee_estimate > 0 && (
            <> {translate("By the agreement you may charge about {v0} for the unused rooms.", { v0: inr(d.attrition.fee_estimate) })}</>
          )}
        </div>
      )}

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(error)}</div>}
      {notice && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</div>}

      {/* tabs */}
      <div className="flex gap-1 border-b border-zinc-200" role="tablist">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            role="tab"
            aria-selected={shownTab === tb.key}
            onClick={() => setTab(tb.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              shownTab === tb.key ? "border-brand-600 text-brand-700" : "border-transparent text-zinc-500 hover:text-zinc-800"
            }`}
          >{tb.label}</button>
        ))}
      </div>

      {/* ------------------------------ GUESTS ------------------------------ */}
      {shownTab === "guests" && (
        <div className="space-y-3">
          {list.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <Button disabled={busy || ciCount === 0} onClick={checkInAll}>
                {translate("Check in ({v0})", { v0: String(ciCount) })}
              </Button>
              <Button
                variant="outline"
                disabled={busy || coCount === 0}
                onClick={() =>
                  groupAction(
                    "kamra.ledger.group_checkout", { group: name },
                    translate("Check out {v0} room(s)? Each guest must have paid their own bill first.", { v0: String(coCount) }),
                    translate("checked out"),
                  )
                }
              >{translate("Check out ({v0})", { v0: String(coCount) })}</Button>
              {noRoomCount > 0 && (
                <Button variant="outline" disabled={busy} onClick={giveRooms}>
                  {translate("Give room numbers ({v0})", { v0: String(noRoomCount) })}
                </Button>
              )}
              <button
                className="text-sm font-medium text-zinc-600 hover:text-zinc-900 disabled:opacity-40"
                disabled={busy || amendCount === 0}
                onClick={() => {
                  setNewDates({ check_in_date: g.check_in_date, check_out_date: g.check_out_date })
                  setDatesOpen((o) => !o)
                }}
              >{translate("Change dates")}</button>
              <button
                className="text-sm font-medium text-rose-600 hover:text-rose-800 disabled:opacity-40"
                disabled={busy || ciCount === 0}
                onClick={() =>
                  groupAction(
                    "kamra.api.group_cancel", { group_booking: name },
                    translate("Cancel {v0} room(s)? The cancellation policy applies to each room.", { v0: String(ciCount) }),
                    translate("cancelled"),
                  )
                }
              >{translate("Cancel rooms")}</button>
              <span className="text-xs text-zinc-400">
                {selected.size
                  ? translate("Only the {v0} ticked room(s)", { v0: String(selected.size) })
                  : translate("All rooms - tick rooms below to act on some")}
              </span>
            </div>
          )}
          {datesOpen && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-zinc-50 px-3 py-2">
              <input type="date" aria-label={translate("New arrival")} className={inputSm}
                value={newDates.check_in_date} onChange={(e) => setNewDates({ ...newDates, check_in_date: e.target.value })} />
              →
              <input type="date" aria-label={translate("New departure")} className={inputSm}
                value={newDates.check_out_date} onChange={(e) => setNewDates({ ...newDates, check_out_date: e.target.value })} />
              <Button
                disabled={busy || !newDates.check_in_date || newDates.check_out_date <= newDates.check_in_date}
                onClick={() => {
                  setDatesOpen(false)
                  groupAction(
                    "kamra.api.group_amend_dates", { group_booking: name, ...newDates, confirm_price: 1 },
                    translate("Move {v0} room(s) to {v1} → {v2}? Each room's price is worked out again for the new dates.", {
                      v0: String(amendCount), v1: newDates.check_in_date, v2: newDates.check_out_date,
                    }),
                    translate("moved"),
                  )
                }}
              >{translate("Apply")}</Button>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <h3 className="flex-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">{translate("Guest list")}</h3>
            {list.some(active) && (
              <>
                <Button variant="outline" disabled={busy} onClick={() => setPasteOpen((o) => !o)}>{translate("Paste from Excel")}</Button>
                <Button disabled={busy || changedNames.length === 0} onClick={saveNames}>
                  {translate("Save names ({v0})", { v0: String(changedNames.length) })}
                </Button>
              </>
            )}
          </div>
          {pasteOpen && (
            <div className="space-y-2 rounded-lg bg-zinc-50 p-3">
              <p className="text-xs text-zinc-500">
                {translate("Paste Name and Phone from Excel, one guest per line. They fill the ticked rooms, or every room, in order.")}
              </p>
              <textarea
                className="h-28 w-full rounded-lg border border-zinc-300 px-3 py-2 font-mono text-sm"
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder={"Priya Sharma, 9876543210\nRahul Mehta, 9123456780"}
              />
              <div className="flex gap-2">
                <Button disabled={!pasteText.trim()} onClick={applyPaste}>{translate("Fill names")}</Button>
                <Button variant="outline" onClick={() => setPasteOpen(false)}>{translate("Close")}</Button>
              </div>
            </div>
          )}

          {list.length === 0 ? (
            <p className="text-sm text-zinc-400">{translate("No guests yet - add them below.")}</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-400">
                  <th className="w-6 py-1 pr-2">
                    <input
                      type="checkbox"
                      aria-label={translate("Tick all rooms")}
                      checked={selected.size > 0 && selected.size === list.length}
                      onChange={(e) => setSelected(e.target.checked ? new Set(list.map((r) => r.name)) : new Set())}
                    />
                  </th>
                  <th className="py-1 pr-3 font-medium">{translate("Guest")}</th>
                  <th className="py-1 pr-3 font-medium">{translate("Room")}</th>
                  <th className="py-1 pr-3 font-medium">{translate("Status")}</th>
                  <th className="py-1 pr-3 text-right font-medium">{translate("Owes")}</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {list.map((r) => (
                  <tr key={r.name} className="align-top">
                    <td className="py-2 pr-2">
                      <input
                        type="checkbox"
                        aria-label={translate("Tick {v0}", { v0: r.guest_name })}
                        checked={selected.has(r.name)}
                        onChange={(e) =>
                          setSelected((s) => {
                            const next = new Set(s)
                            if (e.target.checked) next.add(r.name)
                            else next.delete(r.name)
                            return next
                          })
                        }
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      {active(r) ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1">
                            <input
                              className="w-full min-w-32 rounded-lg border border-zinc-300 px-2 py-1 text-sm font-medium"
                              aria-label={translate("Guest name for {v0}", { v0: r.name })}
                              value={names[r.name]?.guest_name ?? ""}
                              onChange={(e) => setName(r.name, "guest_name", e.target.value)}
                            />
                            {r.is_master && <Star className="size-3.5 shrink-0 text-amber-500" aria-label={translate("Main room")} />}
                          </div>
                          <input
                            className="w-full rounded-lg border border-zinc-200 px-2 py-0.5 text-xs"
                            aria-label={translate("Phone for {v0}", { v0: r.name })}
                            placeholder={translate("Phone")}
                            value={names[r.name]?.phone ?? ""}
                            onChange={(e) => setName(r.name, "phone", e.target.value)}
                          />
                        </div>
                      ) : (
                        <div className="font-medium">
                          {r.guest_name}
                          {r.is_master && <Star className="ml-1 inline size-3.5 text-amber-500" aria-label={translate("Main room")} />}
                          {r.phone && <div className="text-xs font-normal text-zinc-500">{r.phone}</div>}
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-zinc-600">
                      {r.room_type_name}
                      <div className={`text-xs ${r.room ? "text-zinc-500" : "text-amber-700"}`}>
                        {r.room ? translate("Room {v0}", { v0: String(r.room_number ?? short(r.room)) }) : translate("No room number yet")}
                      </div>
                      {(r.check_in_date !== g.check_in_date || r.check_out_date !== g.check_out_date) && (
                        <div className="text-xs text-zinc-500">{r.check_in_date.slice(5)} → {r.check_out_date.slice(5)}</div>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      <Badge tone={STATUS_TONE[r.status] ?? "zinc"}>{translate(r.status)}</Badge>
                    </td>
                    <td className={`py-2 pr-3 text-right ${r.own_balance > 0.5 ? "font-medium text-rose-700" : "text-zinc-400"}`}>
                      {r.own_balance > 0.5 ? inr(r.own_balance) : "-"}
                    </td>
                    <td className="py-1.5 text-right">
                      {r.status === "Confirmed" && (
                        <Button variant="outline" onClick={() => setCheckingIn(r.name)}>{translate("Check in")}</Button>
                      )}
                      {r.status === "Checked In" && unfinished.has(r.name) && (
                        <Button variant="outline" onClick={() => setCheckingIn(r.name)}>{translate("Finish")}</Button>
                      )}
                      {r.status === "Checked In" && (
                        <Button variant="outline" onClick={() => setCheckingOut(r.name)}>
                          {r.own_balance > 0.5 ? translate("Collect & check out") : translate("Check out")}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* add a guest into a room still kept for the group */}
          {g.status === "Confirmed" && stillFree > 0 && (
            <div className="rounded-lg border border-dashed border-zinc-300 p-3">
              <div className="mb-2 text-sm font-medium">
                {translate("Add a guest - {v0} room(s) still kept free for the group", { v0: String(stillFree) })}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select className={inputSm} value={pick.room_type} onChange={(e) => setPick({ ...pick, room_type: e.target.value })}>
                  {d.pickup.filter((p) => p.remaining > 0).map((p) => (
                    <option key={p.room_type} value={p.room_type}>
                      {translate("{v0} ({v1} free)", { v0: p.room_type_name, v1: String(p.remaining) })}
                    </option>
                  ))}
                </select>
                <input className={`${inputSm} min-w-40 flex-1`} placeholder={translate("Guest name")}
                  value={pick.guest_name} onChange={(e) => setPick({ ...pick, guest_name: e.target.value })} />
                <input className={`${inputSm} w-36`} placeholder={translate("Phone")}
                  value={pick.phone} onChange={(e) => setPick({ ...pick, phone: e.target.value })} />
                <Button
                  disabled={busy || !pick.guest_name.trim() || !pick.room_type}
                  onClick={() =>
                    act(async () => {
                      await call("kamra.api.pickup_group_room", {
                        group_booking: name, room_type: pick.room_type,
                        guest_name: pick.guest_name.trim(), phone: pick.phone || null,
                      })
                      setPick((pk) => ({ ...pk, guest_name: "", phone: "" }))
                      setNotice(translate("Guest added."))
                    })
                  }
                ><Plus className="size-4" />{translate("Add guest")}</Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------ ROOMS ------------------------------ */}
      {shownTab === "rooms" && (
        <div className="space-y-4">
          <div>
            <h3 className={sectionTitle}>{translate("Rooms kept for this group")}</h3>
            <div className="space-y-2">
              {blocks.map((b, i) => {
                const p = d.pickup.find((x) => x.room_type === b.room_type)
                const pct = p && p.rooms_blocked > 0 ? Math.round((p.picked_up / p.rooms_blocked) * 100) : 0
                return (
                  <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 p-2">
                    <select
                      className={inputSm}
                      aria-label={translate("Room type")}
                      value={b.room_type}
                      onChange={(e) => setBlocks((bs) => bs.map((x, j) => (j === i ? { ...x, room_type: e.target.value } : x)))}
                    >
                      <option value="">{translate("Room type…")}</option>
                      {d.room_types.map((rt) => <option key={rt.name} value={rt.name}>{rt.room_type_name}</option>)}
                    </select>
                    <label className="flex items-center gap-1 text-xs text-zinc-500">
                      {translate("Rooms")}
                      <input type="number" min={0} className={`${inputSm} w-20`} value={b.rooms_blocked}
                        onChange={(e) => setBlocks((bs) => bs.map((x, j) => (j === i ? { ...x, rooms_blocked: e.target.value } : x)))} />
                    </label>
                    <label className="flex items-center gap-1 text-xs text-zinc-500">
                      {translate("Group rate / night")}
                      <input type="number" min={0} className={`${inputSm} w-28`} placeholder={translate("Normal price")} value={b.block_rate}
                        disabled={!d.can_set_rate}
                        title={d.can_set_rate ? undefined : translate("Only a Revenue Manager or Hotel Admin can set a group rate.")}
                        onChange={(e) => setBlocks((bs) => bs.map((x, j) => (j === i ? { ...x, block_rate: e.target.value } : x)))} />
                    </label>
                    {p && (
                      <div className="flex min-w-40 flex-1 items-center gap-2">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100">
                          <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="whitespace-nowrap text-xs text-zinc-500">
                          {translate("{v0} with guests · {v1} free", { v0: String(p.picked_up), v1: String(p.remaining) })}
                          {Object.keys(p.nightly_counts ?? {}).length > 0 && (
                            <span className="block" title={translate("Rooms per night")}>
                              {Object.entries(p.nightly_counts).map(([date, n]) => `${date.slice(5)}: ${n}`).join(" · ")}
                            </span>
                          )}
                        </span>
                      </div>
                    )}
                    <button aria-label={translate("Remove room type")} onClick={() => setBlocks((bs) => bs.filter((_, j) => j !== i))}
                      className="text-zinc-300 hover:text-rose-500">
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                )
              })}
            </div>
            <Button variant="outline" className="mt-2"
              onClick={() => setBlocks((bs) => [...bs, { room_type: "", rooms_blocked: "", block_rate: "" }])}>
              <Plus className="size-4" />{translate("Add room type")}
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-zinc-600">{translate("Keep free rooms until")}</span>
              <input type="date" className={`${inputSm} w-full`} value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
              <span className="mt-1 block text-xs text-zinc-500">{translate("After this date, rooms without a guest name go back on sale.")}</span>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-zinc-600">{translate("Rooms they can give back free (%)")}</span>
              <input type="number" min={0} max={100} className={`${inputSm} w-full`} placeholder="0"
                value={terms.attrition_pct} onChange={(e) => setTerms({ ...terms, attrition_pct: e.target.value })} />
              <span className="mt-1 block text-xs text-zinc-500">
                {translate("Used so far: {v0}% of the kept room-nights ({v1} of {v2}).", {
                  v0: String(d.attrition.pickup_pct), v1: String(d.attrition.picked_room_nights), v2: String(d.attrition.blocked_room_nights),
                })}
              </span>
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={busy} onClick={() => saveBlocks()}>{translate("Save changes")}</Button>
            {g.status === "Open" && (
              <Button variant="outline" disabled={busy} onClick={() => saveBlocks("Confirmed")}>{translate("Confirm booking")}</Button>
            )}
          </div>

          {d.event && (
            <div className="rounded-lg bg-zinc-50 px-4 py-2.5 text-sm">
              <span className="font-medium">{translate(d.event.event_type)}</span>
              <span className="text-zinc-500">
                {" "}{translate("at ")}{short(d.event.venue)} · {d.event.event_date} · {d.event.attendees}{translate(" pax")}
                {d.event.quoted_amount ? ` · ${inr(d.event.quoted_amount)}` : ""}{" "}
              </span>
              <Badge tone={d.event.status === "Confirmed" ? "green" : "amber"}>{translate(d.event.status)}</Badge>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------- BILL ------------------------------- */}
      {shownTab === "bill" && (
        <div className="space-y-4">
          {/* who pays */}
          <div>
            <h3 className={sectionTitle}>{translate("Who pays")}</h3>
            <div className="space-y-2 rounded-lg border border-zinc-200 p-3 text-sm">
              {g.company ? (
                <p>{translate("Room charges go to {v0}; at the end they are sent to the company account.", { v0: g.company })}</p>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <span>{translate("Main guest who pays for the rooms:")}</span>
                  {list.some(active) ? (
                    <select
                      className={inputSm}
                      value={main?.name ?? ""}
                      disabled={busy}
                      onChange={(e) => e.target.value && act(() => call("kamra.api.set_group_master", { group_booking: name, reservation: e.target.value }))}
                    >
                      <option value="">{translate("Choose…")}</option>
                      {list.filter((r) => active(r) || r.is_master).map((r) => <option key={r.name} value={r.name}>{r.guest_name}</option>)}
                    </select>
                  ) : (
                    <span className="font-medium">{main?.guest_name ?? "-"}</span>
                  )}
                  {g.master_pays && <span className="text-zinc-500">{translate("pays: {v0}", { v0: translate(g.master_pays) })}</span>}
                </div>
              )}
              <p className="text-xs text-zinc-500">
                {translate("Each guest pays their own extras (restaurant, laundry, liquor) on their own bill at check-out.")}
              </p>
            </div>
          </div>

          {/* per guest */}
          {list.length > 0 && (
            <div>
              <h3 className={sectionTitle}>{translate("Each guest's own bill")}</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-400">
                    <th className="py-1 pr-3 font-medium">{translate("Guest")}</th>
                    <th className="py-1 pr-3 text-right font-medium">{translate("Owes")}</th>
                    {g.master_reservation && <th className="py-1 pr-3 font-medium">{translate("Pays own room")}</th>}
                    <th />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {list.map((r) => (
                    <tr key={r.name}>
                      <td className="py-1.5 pr-3">
                        {r.guest_name}
                        {r.is_master && <Star className="ml-1 inline size-3.5 text-amber-500" aria-label={translate("Main room")} />}
                        <span className="ml-1 text-xs text-zinc-400">{translate(r.status)}</span>
                      </td>
                      <td className={`py-1.5 pr-3 text-right ${r.own_balance > 0.5 ? "font-medium text-rose-700" : "text-zinc-400"}`}>
                        {r.own_balance > 0.5 ? inr(r.own_balance) : translate("Nothing")}
                      </td>
                      {g.master_reservation && (
                        <td className="py-1.5 pr-3">
                          {!r.is_master && active(r) && (
                            <input
                              type="checkbox"
                              aria-label={translate("{v0} pays their own room", { v0: r.guest_name })}
                              checked={!!r.pays_own_charges}
                              disabled={busy}
                              onChange={(e) => act(() => call("kamra.api.set_pays_own_charges", { reservation: r.name, value: e.target.checked ? 1 : 0 }))}
                            />
                          )}
                        </td>
                      )}
                      <td className="py-1.5 text-right">
                        {r.status === "Checked In" && (
                          <Button variant="outline" onClick={() => setCheckingOut(r.name)}>
                            {r.own_balance > 0.5 ? translate("Collect & check out") : translate("Check out")}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* the group bill */}
          <div>
            <h3 className={sectionTitle}>{translate("Group bill (room charges)")}</h3>
            <div className="space-y-3 rounded-lg border border-zinc-200 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                {d.master_folio ? (
                  <Link to={`/billing/${encodeURIComponent(d.master_folio)}`} className="font-medium text-brand-700 hover:underline">
                    {d.master_folio_status === "Closed"
                      ? translate("Open group bill (closed) →")
                      : d.master_folio_balance < -0.5
                        ? translate("Open group bill - {v0} in credit →", { v0: inr(-d.master_folio_balance) })
                        : translate("Open group bill - balance {v0} →", { v0: inr(d.master_folio_balance) })}
                  </Link>
                ) : (
                  <span className="text-zinc-500">{translate("The group bill starts when the first room charge or deposit is posted.")}</span>
                )}
                <Link to={`/group-quote/${encodeURIComponent(name)}`} className="font-medium text-brand-700 hover:underline">
                  {translate("Quotation")}
                </Link>
              </div>

              {/* deposit: not once the bill is closed and nobody is left to stay */}
              {(d.master_folio_status !== "Closed" || toArrive + inHouse > 0) && (
              <div className="flex flex-wrap items-center gap-2">
                <span>{translate("Advance paid: {v0}", { v0: inr(d.money.deposits) })}</span>
                <label className="flex items-center gap-1 text-xs text-zinc-500">
                  {translate("asked")}
                  <input type="number" min={0} className={`${inputSm} w-24`} value={terms.deposit_due}
                    onChange={(e) => setTerms({ ...terms, deposit_due: e.target.value })}
                    onBlur={() => Number(terms.deposit_due || 0) !== g.deposit_due && saveBlocks()} />
                </label>
                {!deposit ? (
                  <Button variant="outline" disabled={busy || g.status === "Cancelled"} onClick={openDeposit}>{translate("Take deposit")}</Button>
                ) : (
                  <>
                    <input type="number" aria-label={translate("Deposit amount")} className={`${inputSm} w-28`}
                      value={deposit.amount} onChange={(e) => setDeposit({ ...deposit, amount: e.target.value })} />
                    <select aria-label={translate("Payment mode")} className={inputSm} value={deposit.mode}
                      onChange={(e) => setDeposit({ ...deposit, mode: e.target.value })}>
                      {loc.payment_modes.map((m) => <option key={m} value={m}>{translate(m)}</option>)}
                    </select>
                    <Button disabled={busy || !(Number(deposit.amount) > 0)} onClick={() => takeDeposit(Number(deposit.amount), deposit.mode)}>
                      {translate("Receive")}
                    </Button>
                    <Button variant="outline" onClick={() => setDeposit(null)}>{translate("Cancel")}</Button>
                  </>
                )}
              </div>
              )}

              {/* settle: only when the bill has something to settle */}
              {groupBillDue > 0.5 && !settle && (
                toArrive + inHouse > 0 ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="outline" disabled={busy} onClick={openSettle}>{translate("Settle group bill")}</Button>
                    <span className="text-xs text-amber-700">
                      {translate("{v0} room(s) have not checked out yet. Settle after they leave, unless you mean to bill in parts.", { v0: String(toArrive + inHouse) })}
                    </span>
                  </div>
                ) : (
                  <Button disabled={busy} onClick={openSettle}>{translate("Settle group bill")}</Button>
                )
              )}
              {settle && (
                <div className="space-y-2 rounded-lg bg-zinc-50 p-3">
                  <div className="font-medium">{translate("Settle group bill ({v0})", { v0: inr(groupBillDue) })}</div>
                  {toArrive + inHouse > 0 && (
                    <p className="text-xs text-amber-700">
                      {translate("{v0} room(s) have not checked out yet. Settling now closes this bill, and their room charges start a new group bill.", { v0: String(toArrive + inHouse) })}
                    </p>
                  )}
                  {g.company && (
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={settle.cityLedger} onChange={(e) => setSettle({ ...settle, cityLedger: e.target.checked })} />
                      {translate("Send to the company account (they pay later)")}
                    </label>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    {!settle.cityLedger && (
                      <>
                        <select className={inputSm} value={settle.mode} onChange={(e) => setSettle({ ...settle, mode: e.target.value })}>
                          {loc.payment_modes.map((m) => <option key={m} value={m}>{translate(m)}</option>)}
                        </select>
                        <input type="number" className={`${inputSm} w-32`} value={settle.amount}
                          onChange={(e) => setSettle({ ...settle, amount: e.target.value })} />
                      </>
                    )}
                    <Button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          const out = await call<{ closed: boolean; invoice_number?: string; warning?: string }>(
                            "kamra.api.settle_group_bill",
                            {
                              group_booking: name,
                              mode: settle.cityLedger ? null : settle.mode,
                              amount: settle.cityLedger ? null : Number(settle.amount) || null,
                              to_city_ledger: settle.cityLedger ? 1 : 0,
                            },
                          )
                          setSettle(null)
                          setNotice(
                            [out.closed ? translate("Group bill closed, invoice {v0}.", { v0: out.invoice_number ?? "" }) : "",
                             out.warning ?? ""].filter(Boolean).join(" ") || null,
                          )
                        }, true)
                      }
                    >{settle.cityLedger ? translate("Send to company") : translate("Collect and close")}</Button>
                    <Button variant="outline" onClick={() => setSettle(null)}>{translate("Cancel")}</Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <LinkedRecords doctype="Group Booking" name={name} exclude={["group"]} />
        </div>
      )}

      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
            setNotice(null)
            load()
          }}
        />
      )}
      {checkingOut && (
        <CheckOutDialog
          reservation={checkingOut}
          onClose={() => setCheckingOut(null)}
          onDone={() => {
            setCheckingOut(null)
            setNotice(null)
            load()
          }}
          onOpenReservation={(res) => setCheckingOut(res)}
        />
      )}
    </div>
  )
}
