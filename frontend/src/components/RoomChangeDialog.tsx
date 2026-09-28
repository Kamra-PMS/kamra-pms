/*  Change a booking's room from wherever the desk is - the reservation
    drawer or the GRC - not only the tape chart (#113). Same writer and the
    same availability rules as the tape chart (movable_rooms / move_reservation);
    the price effect is previewed before anything changes. */

import { useEffect, useMemo, useState } from "react"
import { ArrowRight, BedDouble, Loader2, Search, X } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { cur, moneyLocale } from "../lib/money"
import { useT } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"

interface MovableRoom {
  name: string
  room_number: string
  room_type: string
  room_type_name: string
  floor: string | null
  housekeeping_status: string | null
  free: boolean
  same_type: boolean
  current: boolean
}

interface Preview {
  same_type: boolean
  new_room_type_name: string | null
  current_amount: number
  new_amount: number
  difference: number
  auto_price: boolean
  in_house: boolean
}

const REASONS = ["Guest request", "Upgrade", "Maintenance", "Noise / complaint", "Other"]

const hkTone: Record<string, string> = {
  Clean: "bg-emerald-50 text-emerald-700",
  Inspected: "bg-sky-50 text-sky-700",
  Dirty: "bg-amber-50 text-amber-700",
  "Out of Order": "bg-rose-50 text-rose-700",
}

const money = (n: number) =>
  `${cur()}${Math.abs(n).toLocaleString(moneyLocale(), { maximumFractionDigits: 2 })}`

export default function RoomChangeDialog(props: {
  reservation: string
  currentRoomNumber?: string | null
  onClose: () => void
  onMoved: (r: { room: string; room_type: string }) => void
}) {
  const { t } = useT()
  const [rooms, setRooms] = useState<MovableRoom[] | null>(null)
  const [scope, setScope] = useState<"same" | "all">("same")
  const [q, setQ] = useState("")
  const [pick, setPick] = useState<MovableRoom | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [reason, setReason] = useState(REASONS[0])
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<MovableRoom[]>("kamra.api.movable_rooms", { reservation: props.reservation })
      .then(setRooms)
      .catch((e) => setError(serverError(e)))
  }, [props.reservation])

  useEffect(() => {
    setPreview(null)
    if (!pick) return
    let live = true
    call<Preview>("kamra.api.room_move_preview", {
      reservation: props.reservation,
      new_room: pick.name,
    })
      .then((p) => live && setPreview(p))
      .catch((e) => live && setError(serverError(e)))
    return () => {
      live = false
    }
  }, [pick, props.reservation])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && props.onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [props])

  const shown = useMemo(() => {
    const list = (rooms ?? []).filter(
      (r) =>
        !r.current &&
        (scope === "all" || r.same_type) &&
        (!q.trim() || r.room_number.toLowerCase().includes(q.trim().toLowerCase())),
    )
    // free and clean first - the room the desk most likely wants
    const rank = (r: MovableRoom) =>
      (r.free ? 0 : 2) + (r.housekeeping_status === "Clean" || r.housekeeping_status === "Inspected" ? 0 : 1)
    return [...list].sort((a, b) => rank(a) - rank(b))
  }, [rooms, scope, q])

  const groups = useMemo(() => {
    const m = new Map<string, MovableRoom[]>()
    for (const r of shown) {
      const k = r.room_type_name
      m.set(k, [...(m.get(k) ?? []), r])
    }
    return [...m.entries()]
  }, [shown])

  async function confirm() {
    if (!pick) return
    setBusy(true)
    setError(null)
    try {
      const r = await call<{ room: string; room_type: string }>("kamra.api.move_reservation", {
        reservation: props.reservation,
        new_room: pick.name,
        reason: note.trim() ? `${reason}: ${note.trim()}` : reason,
      })
      props.onMoved(r)
      props.onClose()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const freeCount = (rooms ?? []).filter((r) => r.free && !r.current).length

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={t("Change room")}>
      <div className="absolute inset-0 bg-black/40" onClick={props.onClose} aria-hidden />
      <div className="relative flex max-h-[90dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900">{t("Change room")}</h2>
            <p className="text-sm text-zinc-500">
              {props.currentRoomNumber
                ? t("Now in {room} · {n} rooms free for these dates", {
                    room: props.currentRoomNumber,
                    n: freeCount,
                  })
                : t("{n} rooms free for these dates", { n: freeCount })}
            </p>
          </div>
          <Button variant="ghost" onClick={props.onClose} aria-label={t("Close")}>
            <X className="size-5" />
          </Button>
        </header>

        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-5 py-3">
          <div role="radiogroup" aria-label={t("Room types")} className="inline-flex rounded-lg bg-zinc-100 p-0.5 text-sm">
            {(
              [
                ["same", t("Same type")],
                ["all", t("All types (upgrade)")],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                role="radio"
                aria-checked={scope === k}
                onClick={() => setScope(k)}
                className={cn(
                  "rounded-md px-3 py-1.5 font-medium",
                  scope === k ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="relative ml-auto">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-zinc-400" aria-hidden />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("Room no.")}
              aria-label={t("Search room number")}
              className="w-32 rounded-lg border border-zinc-300 py-2 pl-8 pr-2 text-sm focus:outline-2 focus:outline-brand-600"
            />
          </label>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {!rooms && !error && (
            <p className="flex items-center gap-2 text-sm text-zinc-400">
              <Loader2 className="size-4 animate-spin" aria-hidden /> {t("Loading…")}
            </p>
          )}
          {rooms && groups.length === 0 && (
            <p className="py-6 text-center text-sm text-zinc-400">
              {scope === "same"
                ? t("No other room of this type - try All types.")
                : t("No rooms match.")}
            </p>
          )}
          <div className="space-y-4">
            {groups.map(([type, list]) => (
              <div key={type}>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">{type}</p>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                  {list.map((r) => (
                    <button
                      key={r.name}
                      type="button"
                      disabled={!r.free}
                      aria-pressed={pick?.name === r.name}
                      onClick={() => setPick(r)}
                      title={r.free ? undefined : t("Booked for these dates")}
                      className={cn(
                        "rounded-lg border px-2.5 py-2 text-left transition-colors",
                        !r.free && "cursor-not-allowed border-dashed border-zinc-200 bg-zinc-50 opacity-50",
                        r.free && pick?.name !== r.name && "border-zinc-200 hover:border-zinc-400",
                        pick?.name === r.name && "border-brand-600 bg-brand-50 ring-2 ring-brand-600/30",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-zinc-900">{r.room_number}</span>
                        {!r.free && <BedDouble className="size-3.5 text-zinc-400" aria-hidden />}
                      </div>
                      <span
                        className={cn(
                          "mt-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium",
                          r.free ? hkTone[r.housekeeping_status ?? ""] ?? "bg-zinc-100 text-zinc-600" : "bg-zinc-100 text-zinc-500",
                        )}
                      >
                        {r.free ? t(r.housekeeping_status || "—") : t("Booked")}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <footer className="space-y-3 border-t border-zinc-200 bg-zinc-50 px-5 py-4">
          {pick && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <span className="font-medium text-zinc-900">
                {props.currentRoomNumber ?? "—"} <ArrowRight className="inline size-3.5" aria-hidden /> {pick.room_number}
              </span>
              {preview ? (
                preview.difference === 0 ? (
                  <span className="text-zinc-500">{t("No change to the price.")}</span>
                ) : (
                  <span className={preview.difference > 0 ? "text-amber-700" : "text-emerald-700"}>
                    {preview.difference > 0
                      ? t("{type}: stay total +{amt} (now {total})", {
                          type: preview.new_room_type_name ?? "",
                          amt: money(preview.difference),
                          total: money(preview.new_amount),
                        })
                      : t("{type}: stay total -{amt} (now {total})", {
                          type: preview.new_room_type_name ?? "",
                          amt: money(preview.difference),
                          total: money(preview.new_amount),
                        })}
                  </span>
                )
              ) : (
                <Loader2 className="size-4 animate-spin text-zinc-400" aria-label={t("Checking price")} />
              )}
              {preview?.in_house && (
                <span className="basis-full text-xs text-zinc-500">
                  {t("The guest is in-house: the old room is marked Dirty for housekeeping.")}
                </span>
              )}
              {pick.housekeeping_status && !["Clean", "Inspected"].includes(pick.housekeeping_status) && (
                <span className="basis-full text-xs text-amber-700">
                  {t("{room} hasn't been cleaned yet.", { room: pick.room_number })}
                </span>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              aria-label={t("Reason")}
              className="rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-sm"
            >
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(r)}
                </option>
              ))}
            </select>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("Note (optional)")}
              className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-sm"
            />
            <Button disabled={!pick || !preview || busy} onClick={confirm}>
              {busy ? t("Moving…") : pick ? t("Move to {room}", { room: pick.room_number }) : t("Pick a room")}
            </Button>
          </div>
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
          )}
        </footer>
      </div>
    </div>
  )
}
