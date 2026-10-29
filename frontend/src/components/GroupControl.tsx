import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Star, Trash2 } from "lucide-react"

import { call } from "../lib/api"
import { useRealtime } from "../lib/realtime"
import { listResource, serverError, type Row } from "../lib/resource"
import LinkedRecords from "./LinkedRecords"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"
import { useCashierAuth } from "../lib/cashierAuth"
import CheckInDialog from "./CheckInDialog"
import CheckOutDialog from "./CheckOutDialog"

/** Group Rooms Control - the MICE cockpit for one piece of business:
 *  the room block (with pickup progress), the rooming list, the tied
 *  banquet event and the group master folio. */

interface PickupRow {
  room_type: string
  rooms_blocked: number
  block_rate: number
  picked_up: number
  remaining: number
}
interface Detail {
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
  }
  pickup: PickupRow[]
  rooming_list: {
    name: string
    guest_name: string
    room_type: string
    room: string | null
    room_number: string | null
    status: string
    check_in_date: string
    pays_own_charges: 0 | 1
    is_master: boolean
  }[]
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

interface GroupCheckIn {
  checked_in: { reservation: string; guest_name: string; pending: string[] }[]
  skipped: { reservation: string; guest_name: string; reason: string }[]
  to_finish: number
}

interface BlockDraft {
  room_type: string
  rooms_blocked: string
  block_rate: string
}

const short = (rt: string) => rt.split("-").pop() ?? rt
const inr = (n: number) =>
  `${cur()}` + Number(n || 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

const STATUS_TONE: Record<string, "green" | "amber" | "zinc"> = {
  Confirmed: "green",
  Open: "amber",
  Cancelled: "zinc",
}

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
  const [roomTypes, setRoomTypes] = useState<string[]>([])
  const [blocks, setBlocks] = useState<BlockDraft[]>([])
  const [cutoff, setCutoff] = useState("")
  const [pick, setPick] = useState({ room_type: "", guest_name: "", phone: "" })
  const [settle, setSettle] = useState<{ mode: string; amount: string; cityLedger: boolean } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [checkingIn, setCheckingIn] = useState<string | null>(null)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [groupIn, setGroupIn] = useState<"ask" | GroupCheckIn | null>(null)
  const loc = useLocale()
  const { ensureUnlocked, status: pinStatus } = useCashierAuth()

  const load = useCallback(() => {
    call<Detail>("kamra.api.group_detail", { group_booking: name })
      .then((r) => {
        setD(r)
        setBlocks(
          r.pickup.map((p) => ({
            room_type: p.room_type,
            rooms_blocked: String(p.rooms_blocked),
            block_rate: p.block_rate ? String(p.block_rate) : "",
          })),
        )
        setCutoff(r.group.cutoff_date ?? "")
        setPick((pk) => ({ ...pk, room_type: r.pickup[0]?.room_type ?? "" }))
      })
      .catch((e) => setError(serverError(e)))
  }, [name])
  useEffect(load, [load])
  useRealtime(load)

  useEffect(() => {
    listResource("Room Type", { fields: ["name"], limit: 50 })
      .then((rows) => setRoomTypes(rows.map((r) => String(r.name))))
      .catch(() => {})
  }, [])

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
    act(() =>
      call("kamra.api.save_group_blocks", {
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
      }),
    )

  if (!d)
    return (
      <p className="py-8 text-center text-sm text-zinc-400">
        {translate(error) ?? translate("Loading group…")}
      </p>
    )

  const g = d.group
  // ponytail: the browser's date; the server checks against the business date
  const today = new Date().toLocaleDateString("en-CA")
  const arriving = d.rooming_list.filter((r) => r.status === "Confirmed" && r.check_in_date <= today).length
  const unfinished = new Set(groupIn && groupIn !== "ask"
    ? groupIn.checked_in.filter((x) => x.pending.length).map((x) => x.reservation) : [])
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold">{g.group_name}</div>
          <div className="text-sm text-zinc-500">
            {g.check_in_date} → {g.check_out_date}
            {g.company && <> · {g.company}</>}
          </div>
        </div>
        <Badge tone={STATUS_TONE[g.status] ?? "zinc"}>{translate(g.status)}</Badge>
        {g.status === "Open" && (
          <Button disabled={busy} onClick={() => saveBlocks("Confirmed")}>{translate("Confirm block")}</Button>
        )}
        {d.master_folio ? (
          <>
            <Link
              to={`/billing/${encodeURIComponent(d.master_folio)}`}
              className="text-sm font-medium text-brand-700 hover:underline"
            >{translate("Open group bill ({v0}) →", { v0: inr(d.master_folio_balance) })}</Link>
            {d.master_folio_status === "Open" && !settle && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  setSettle({
                    mode: loc.payment_modes[0] ?? "Cash",
                    amount: String(d.master_folio_balance || ""),
                    cityLedger: false,
                  })
                }
              >{translate("Settle group bill")}</Button>
            )}
          </>
        ) : (
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(() =>
                call("kamra.api.group_master_folio", { group_booking: name }),
              )
            }
          >{translate("Open group folio")}</Button>
        )}
      </div>

      {g.master_reservation && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-600">
          <Badge tone="green"><Star className="mr-1 inline size-3" aria-hidden />{translate("Main room")}</Badge>
          {(() => {
            const m = d.rooming_list.find((r) => r.is_master)
            return m ? `${m.guest_name}${m.room_number ? ` · ${m.room_number}` : ""}` : g.master_reservation
          })()}
          {g.master_pays && <span className="text-zinc-400">· {translate("pays: {v0}", { v0: translate(g.master_pays) })}</span>}
        </div>
      )}

      {settle && (
        <div className="space-y-2 rounded-lg border border-zinc-200 p-3">
          <div className="text-sm font-medium">{translate("Settle group bill")}</div>
          {g.in_house > 0 && (
            <p className="text-xs text-amber-700">
              {translate("{v0} room(s) are still in house. Their new charges open a new group bill.", { v0: String(g.in_house) })}
            </p>
          )}
          {g.company && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settle.cityLedger}
                onChange={(e) => setSettle({ ...settle, cityLedger: e.target.checked })}
              />
              {translate("Send to the company's city ledger")}
            </label>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {!settle.cityLedger && (
              <>
                <select
                  className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  value={settle.mode}
                  onChange={(e) => setSettle({ ...settle, mode: e.target.value })}
                >
                  {loc.payment_modes.map((m) => (
                    <option key={m} value={m}>{translate(m)}</option>
                  ))}
                </select>
                <input
                  type="number"
                  className="w-32 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  value={settle.amount}
                  onChange={(e) => setSettle({ ...settle, amount: e.target.value })}
                />
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
            >{translate("Settle")}</Button>
            <Button variant="outline" onClick={() => setSettle(null)}>{translate("Cancel")}</Button>
          </div>
        </div>
      )}
      {notice && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-800">{notice}</div>
      )}

      <LinkedRecords doctype="Group Booking" name={name} exclude={["group"]} />

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}

      {/* block editor + pickup */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">{translate("Room block")}</h3>
          <label className="flex items-center gap-2 text-xs text-zinc-500">{translate("Cutoff")}<input
              type="date"
              className="rounded-lg border border-zinc-300 px-2 py-1 text-xs"
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
              title={translate("Unsold blocked rooms release back to sale after this date")}
            />
          </label>
        </div>
        <div className="space-y-2">
          {blocks.map((b, i) => {
            const p = d.pickup.find((x) => x.room_type === b.room_type)
            const pct = p && p.rooms_blocked > 0
              ? Math.round((p.picked_up / p.rooms_blocked) * 100)
              : 0
            return (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <select
                  className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  value={b.room_type}
                  onChange={(e) =>
                    setBlocks((bs) =>
                      bs.map((x, j) =>
                        j === i ? { ...x, room_type: e.target.value } : x,
                      ),
                    )
                  }
                >
                  <option value="">{translate("Room type…")}</option>
                  {roomTypes.map((rt) => (
                    <option key={rt} value={rt}>
                      {short(rt)}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  className="w-20 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  placeholder={translate("Rooms")}
                  value={b.rooms_blocked}
                  onChange={(e) =>
                    setBlocks((bs) =>
                      bs.map((x, j) =>
                        j === i ? { ...x, rooms_blocked: e.target.value } : x,
                      ),
                    )
                  }
                />
                <input
                  type="number"
                  className="w-28 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  placeholder={translate("{v0}/night", { v0: String(cur()) })}
                  value={b.block_rate}
                  onChange={(e) =>
                    setBlocks((bs) =>
                      bs.map((x, j) =>
                        j === i ? { ...x, block_rate: e.target.value } : x,
                      ),
                    )
                  }
                />
                {p && (
                  <div className="flex min-w-40 flex-1 items-center gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100">
                      <div
                        className="h-full rounded-full bg-brand-600"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="whitespace-nowrap text-xs text-zinc-500">
                      {p.picked_up}/{p.rooms_blocked}{translate(" picked · ")}{p.remaining}{" "}{translate("left")}</span>
                  </div>
                )}
                <button
                  aria-label={translate("Remove block row")}
                  onClick={() =>
                    setBlocks((bs) => bs.filter((_, j) => j !== i))
                  }
                  className="text-zinc-300 hover:text-rose-500"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            )
          })}
        </div>
        <div className="mt-2 flex gap-2">
          <Button
            variant="outline"
            onClick={() =>
              setBlocks((bs) => [
                ...bs,
                { room_type: "", rooms_blocked: "", block_rate: "" },
              ])
            }
          >
            <Plus className="size-4" />{translate(" Add room type")}</Button>
          <Button variant="outline" disabled={busy} onClick={() => saveBlocks()}>{translate("Save block")}</Button>
        </div>
      </div>

      {/* pickup a guest */}
      {g.status === "Confirmed" && d.pickup.some((p) => p.remaining > 0) && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">{translate("Pick up a room")}</h3>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
              value={pick.room_type}
              onChange={(e) => setPick({ ...pick, room_type: e.target.value })}
            >
              {d.pickup
                .filter((p) => p.remaining > 0)
                .map((p) => (
                  <option key={p.room_type} value={p.room_type}>
                    {short(p.room_type)} ({p.remaining}{translate(" left)")}</option>
                ))}
            </select>
            <input
              className="min-w-40 flex-1 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
              placeholder={translate("Guest name")}
              value={pick.guest_name}
              onChange={(e) => setPick({ ...pick, guest_name: e.target.value })}
            />
            <input
              className="w-36 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
              placeholder={translate("Phone")}
              value={pick.phone}
              onChange={(e) => setPick({ ...pick, phone: e.target.value })}
            />
            <Button
              disabled={busy || !pick.guest_name.trim() || !pick.room_type}
              onClick={() =>
                act(async () => {
                  await call("kamra.api.pickup_group_room", {
                    group_booking: name,
                    room_type: pick.room_type,
                    guest_name: pick.guest_name.trim(),
                    phone: pick.phone || null,
                  })
                  setPick((pk) => ({ ...pk, guest_name: "", phone: "" }))
                })
              }
            >{translate("Pick up")}</Button>
          </div>
        </div>
      )}

      {/* event */}
      {d.event && (
        <div className="rounded-lg bg-zinc-50 px-4 py-2.5 text-sm">
          <span className="font-medium">{translate(d.event.event_type)}</span>
          <span className="text-zinc-500">
            {" "}{translate("at ")}{short(d.event.venue)} · {d.event.event_date} ·{" "}
            {d.event.attendees}{translate(" pax")}{d.event.quoted_amount ? ` · ${inr(d.event.quoted_amount)}` : ""} ·{" "}
          </span>
          <Badge tone={d.event.status === "Confirmed" ? "green" : "amber"}>
            {translate(d.event.status)}
          </Badge>
        </div>
      )}

      {/* rooming list */}
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">{translate("Rooming list (")}{d.rooming_list.length})
          </h3>
          {arriving > 0 && groupIn === null && (
            <Button disabled={busy} onClick={() => setGroupIn("ask")}>
              {translate("Check in the group ({n})", { n: String(arriving) })}
            </Button>
          )}
        </div>
        {groupIn === "ask" && (
          <div className="mb-3 rounded-xl border border-brand-200 bg-brand-50/50 p-3 text-sm">
            <p>{translate("Check in all {n} rooms arriving now? A room not given yet gets a free room of the booked type. IDs, deposits and the registration card can be finished room by room afterwards.", { n: String(arriving) })}</p>
            <div className="mt-2 flex gap-2">
              <Button disabled={busy} onClick={() =>
                act(async () => setGroupIn(await call<GroupCheckIn>("kamra.api.group_check_in", { group_booking: name })))
              }>{translate("Check them in")}</Button>
              <Button variant="outline" disabled={busy} onClick={() => setGroupIn(null)}>{translate("Cancel")}</Button>
            </div>
          </div>
        )}
        {groupIn && groupIn !== "ask" && (
          <div className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
            <p className="font-semibold">
              {translate("{n} rooms checked in.", { n: String(groupIn.checked_in.length) })}
              {groupIn.to_finish > 0 && " " + translate("{n} still need IDs or other steps: use Finish on each room.", { n: String(groupIn.to_finish) })}
            </p>
            {groupIn.skipped.map((x) => (
              <p key={x.reservation} className="mt-1 text-rose-700">{x.guest_name}: {x.reason}</p>
            ))}
            <button className="mt-1 text-xs font-medium text-emerald-800 hover:underline" onClick={() => setGroupIn(null)}>
              {translate("Close")}
            </button>
          </div>
        )}
        {d.rooming_list.length === 0 ? (
          <p className="text-sm text-zinc-400">{translate("No guests named into the block yet.")}</p>
        ) : (
          <table className="w-full text-sm">
            <tbody className="divide-y divide-zinc-100">
              {d.rooming_list.map((r) => (
                <tr key={r.name}>
                  <td className="py-1.5 pr-3 font-medium">
                    {r.guest_name}
                    {r.is_master && (
                      <Star className="ml-1 inline size-3.5 text-amber-500" aria-label={translate("Main room")} />
                    )}
                  </td>
                  <td className="py-1.5 pr-3 text-zinc-500">
                    {short(r.room_type)}
                    {r.room ? translate(" · Room {v0}", { v0: String(r.room_number ?? short(r.room)) }) : ""}
                  </td>
                  <td className="py-1.5 pr-3">
                    <Badge
                      tone={
                        r.status === "Checked In"
                          ? "green"
                          : r.status === "Confirmed"
                            ? "amber"
                            : "zinc"
                      }
                    >
                      {translate(r.status)}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-3 text-xs text-zinc-400">
                    {r.name}
                  </td>
                  <td className="py-1.5 text-right">
                    <div className="flex flex-wrap items-center justify-end gap-2 text-xs">
                      {r.status === "Confirmed" && (
                        <Button variant="outline" onClick={() => setCheckingIn(r.name)}>{translate("Check in")}</Button>
                      )}
                      {r.status === "Checked In" && unfinished.has(r.name) && (
                        <Button variant="outline" onClick={() => setCheckingIn(r.name)}>{translate("Finish")}</Button>
                      )}
                      {r.status === "Checked In" && (
                        <Button variant="outline" onClick={() => setCheckingOut(r.name)}>{translate("Check out")}</Button>
                      )}
                      {!r.is_master && ["Confirmed", "Checked In"].includes(r.status) && (
                        <button
                          className="font-medium text-brand-700 hover:underline disabled:opacity-50"
                          disabled={busy}
                          onClick={() =>
                            act(() => call("kamra.api.set_group_master", { group_booking: name, reservation: r.name }))
                          }
                        >{translate("Make main room")}</button>
                      )}
                      {g.master_reservation && !r.is_master && (
                        <label className="flex items-center gap-1 text-zinc-500" title={translate("New charges of this room stay on its own bill")}>
                          <input
                            type="checkbox"
                            checked={!!r.pays_own_charges}
                            disabled={busy}
                            onChange={(e) =>
                              act(() =>
                                call("kamra.api.set_pays_own_charges", {
                                  reservation: r.name,
                                  value: e.target.checked ? 1 : 0,
                                }),
                              )
                            }
                          />
                          {translate("Pays own charges")}
                        </label>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {checkingIn && (
        <CheckInDialog
          reservation={checkingIn}
          onClose={() => setCheckingIn(null)}
          onDone={() => {
            setCheckingIn(null)
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
            load()
          }}
          onOpenReservation={(res) => setCheckingOut(res)}
        />
      )}
    </div>
  )
}
