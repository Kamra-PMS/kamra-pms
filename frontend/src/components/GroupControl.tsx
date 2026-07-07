import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Trash2 } from "lucide-react"

import { call } from "../lib/api"
import { listResource, serverError, type Row } from "../lib/resource"
import LinkedRecords from "./LinkedRecords"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"

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
  }
  pickup: PickupRow[]
  rooming_list: {
    name: string
    guest_name: string
    room_type: string
    room: string | null
    status: string
    check_in_date: string
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
}

interface BlockDraft {
  room_type: string
  rooms_blocked: string
  block_rate: string
}

const short = (rt: string) => rt.split("-").pop() ?? rt
const inr = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

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
  const name = String(row.name)
  const [d, setD] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [roomTypes, setRoomTypes] = useState<string[]>([])
  const [blocks, setBlocks] = useState<BlockDraft[]>([])
  const [cutoff, setCutoff] = useState("")
  const [pick, setPick] = useState({ room_type: "", guest_name: "", phone: "" })

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

  useEffect(() => {
    listResource("Room Type", { fields: ["name"], limit: 50 })
      .then((rows) => setRoomTypes(rows.map((r) => String(r.name))))
      .catch(() => {})
  }, [])

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
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
        {error ?? "Loading group…"}
      </p>
    )

  const g = d.group
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
        <Badge tone={STATUS_TONE[g.status] ?? "zinc"}>{g.status}</Badge>
        {g.status === "Open" && (
          <Button disabled={busy} onClick={() => saveBlocks("Confirmed")}>
            Confirm block
          </Button>
        )}
        {d.master_folio ? (
          <Link
            to={`/billing/${encodeURIComponent(d.master_folio)}`}
            className="text-sm font-medium text-brand-700 hover:underline"
          >
            Group folio →
          </Link>
        ) : (
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(() =>
                call("kamra.api.group_master_folio", { group_booking: name }),
              )
            }
          >
            Open group folio
          </Button>
        )}
      </div>

      <LinkedRecords doctype="Group Booking" name={name} exclude={["group"]} />

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* block editor + pickup */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Room block
          </h3>
          <label className="flex items-center gap-2 text-xs text-zinc-500">
            Cutoff
            <input
              type="date"
              className="rounded-lg border border-zinc-300 px-2 py-1 text-xs"
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
              title="Unsold blocked rooms release back to sale after this date"
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
                  <option value="">Room type…</option>
                  {roomTypes.map((rt) => (
                    <option key={rt} value={rt}>
                      {short(rt)}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  className="w-20 rounded-lg border border-zinc-300 px-2 py-1.5 text-sm"
                  placeholder="Rooms"
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
                  placeholder="₹/night"
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
                      {p.picked_up}/{p.rooms_blocked} picked · {p.remaining}{" "}
                      left
                    </span>
                  </div>
                )}
                <button
                  aria-label="Remove block row"
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
            <Plus className="size-4" /> Add room type
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => saveBlocks()}>
            Save block
          </Button>
        </div>
      </div>

      {/* pickup a guest */}
      {g.status === "Confirmed" && d.pickup.some((p) => p.remaining > 0) && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Pick up a room
          </h3>
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
                    {short(p.room_type)} ({p.remaining} left)
                  </option>
                ))}
            </select>
            <input
              className="min-w-40 flex-1 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
              placeholder="Guest name"
              value={pick.guest_name}
              onChange={(e) => setPick({ ...pick, guest_name: e.target.value })}
            />
            <input
              className="w-36 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
              placeholder="Phone"
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
            >
              Pick up
            </Button>
          </div>
        </div>
      )}

      {/* event */}
      {d.event && (
        <div className="rounded-lg bg-zinc-50 px-4 py-2.5 text-sm">
          <span className="font-medium">{d.event.event_type}</span>
          <span className="text-zinc-500">
            {" "}
            at {short(d.event.venue)} · {d.event.event_date} ·{" "}
            {d.event.attendees} pax
            {d.event.quoted_amount ? ` · ${inr(d.event.quoted_amount)}` : ""} ·{" "}
          </span>
          <Badge tone={d.event.status === "Confirmed" ? "green" : "amber"}>
            {d.event.status}
          </Badge>
        </div>
      )}

      {/* rooming list */}
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Rooming list ({d.rooming_list.length})
        </h3>
        {d.rooming_list.length === 0 ? (
          <p className="text-sm text-zinc-400">
            No guests named into the block yet.
          </p>
        ) : (
          <table className="w-full text-sm">
            <tbody className="divide-y divide-zinc-100">
              {d.rooming_list.map((r) => (
                <tr key={r.name}>
                  <td className="py-1.5 pr-3 font-medium">{r.guest_name}</td>
                  <td className="py-1.5 pr-3 text-zinc-500">
                    {short(r.room_type)}
                    {r.room ? ` · Room ${short(r.room)}` : ""}
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
                      {r.status}
                    </Badge>
                  </td>
                  <td className="py-1.5 text-right text-xs text-zinc-400">
                    {r.name}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
