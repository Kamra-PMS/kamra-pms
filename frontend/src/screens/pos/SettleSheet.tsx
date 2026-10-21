/**
 * Hotel-aware settle overlay: amount-first, large tender buttons, room
 * charge and complimentary close. Opens over the till (POSNext-style pay
 * dialog) so the bill column stays readable.
 */
import { useEffect, useState } from "react"
import { BedDouble, Gift, X } from "lucide-react"
import { Button } from "../../components/ui/button"
import { cn } from "../../lib/utils"
import { useT } from "../../lib/i18n"

export interface SettleRoom {
  room: string
  room_number: string
  guest_name: string | null
  reservation: string
  room_charges_allowed?: 0 | 1
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function SettleSheet({
  subtitle,
  grandLabel,
  zeroLabel,
  modes,
  busy,
  nc,
  room,
  rooms,
  postRoom,
  onPostRoom,
  onLoadRooms,
  sheetNc,
  ncBy,
  ncNote,
  onNcBy,
  onNcNote,
  onSheetNc,
  onSettle,
  onSettleDeliver,
  onChargeToRoom,
  onSettleNc,
  onClose,
}: {
  subtitle: string
  grandLabel: string
  zeroLabel: string
  modes: string[]
  busy: boolean
  nc: boolean
  room: string | null
  rooms: SettleRoom[]
  postRoom: string
  onPostRoom: (room: string) => void
  onLoadRooms: () => void
  sheetNc: boolean
  ncBy: string
  ncNote: string
  onNcBy: (v: string) => void
  onNcNote: (v: string) => void
  onSheetNc: (v: boolean) => void
  onSettle: (mode: string) => void
  onSettleDeliver: () => void
  onChargeToRoom: () => void
  onSettleNc: () => void
  onClose: () => void
}) {
  const { t } = useT()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const [pendingMode, setPendingMode] = useState<string | null>(null) // tender picked, not yet confirmed
  const roomNo = room?.split("-").pop() || ""
  const roomBlocked =
    !!room &&
    Number(rooms.find((r) => r.room === room)?.room_charges_allowed ?? 1) === 0

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center p-3 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settle-title"
    >
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onClose} aria-hidden />
      <div className="relative z-10 flex w-full max-w-md flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl animate-sheet-in">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{t("Settle")}</p>
            <h2
              id="settle-title"
              className="mt-0.5 text-3xl font-semibold tracking-tight tabular-nums text-zinc-900"
            >
              {grandLabel}
            </h2>
            <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
            aria-label={t("Close")}
            onClick={onClose}
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="space-y-3 p-5">
          {nc ? (
            <Button className="h-14 w-full text-base" disabled={busy} onClick={onSettleDeliver}>
              <Gift className="size-5" />
              {t("Close complimentary bill")} · {zeroLabel}
            </Button>
          ) : sheetNc ? (
            <div className="space-y-3">
              <p className="text-sm font-medium text-amber-800">
                {t("Complimentary (no charge) - who authorized?")}
              </p>
              <div className="flex gap-2">
                <select
                  className={inputCls + " !w-28"}
                  value={ncBy}
                  onChange={(e) => onNcBy(e.target.value)}
                >
                  {["Captain", "Chef", "Manager", "GM", "Management", "Owner"].map((w) => (
                    <option key={w}>{w}</option>
                  ))}
                </select>
                <input
                  autoFocus
                  className={inputCls}
                  placeholder={t("Reference (birthday, complaint #, promo…)")}
                  value={ncNote}
                  onChange={(e) => onNcNote(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onSettleNc()}
                />
              </div>
              <div className="flex gap-2">
                <Button className="h-12 flex-1" disabled={busy} onClick={onSettleNc}>
                  <Gift className="size-4" />
                  {t("Mark NC & close")} · {zeroLabel}
                </Button>
                <Button variant="ghost" className="h-12" onClick={() => onSheetNc(false)}>
                  {t("Back")}
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className={cn("grid gap-2", modes.length > 2 ? "grid-cols-3" : "grid-cols-2")}>
                {modes.map((m) => (
                  <Button
                    key={m}
                    variant={pendingMode === m ? "primary" : "outline"}
                    className="h-14 justify-center text-base font-semibold"
                    disabled={busy}
                    onClick={() => setPendingMode(pendingMode === m ? null : m)}
                  >
                    {m}
                  </Button>
                ))}
              </div>
              {pendingMode && (
                <Button className="h-14 w-full text-base" disabled={busy} onClick={() => onSettle(pendingMode)}>
                  {t("Confirm {mode} · {amount}", { mode: pendingMode, amount: grandLabel })}
                </Button>
              )}

              {room ? (
                roomBlocked ? (
                  <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-800">
                    {t("Room {n} cannot take room charges (set at check-in). Take payment here.", {
                      n: roomNo,
                    })}
                  </p>
                ) : (
                  <Button
                    variant="outline"
                    className="h-12 w-full text-base"
                    disabled={busy}
                    onClick={onSettleDeliver}
                  >
                    <BedDouble className="size-5" />
                    {t("Deliver and post to Room {n}", { n: roomNo })}
                  </Button>
                )
              ) : (
                /* a guest who wants it on the room: its own way to settle,
                   for any bill (dine in, takeaway, delivery), not hidden */
                <div className="space-y-1.5 rounded-xl border border-brand-200 bg-white p-2.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-800">
                    <BedDouble className="size-3.5" />
                    {t("Charge to the guest's room")}
                  </div>
                  {rooms.length > 0 ? (
                    <div className="flex gap-2">
                      <RoomPicker
                        rooms={rooms}
                        value={postRoom}
                        onChange={onPostRoom}
                        onOpen={onLoadRooms}
                        placeholder={t("Pick the room…")}
                      />
                      <Button className="h-11 shrink-0" disabled={busy || !postRoom} onClick={onChargeToRoom}>
                        {t("Post to room")}
                      </Button>
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-500">
                      {t("No guest is checked in right now. Check the guest in first, or take payment above.")}
                    </p>
                  )}
                </div>
              )}

              <Button
                variant="outline"
                className="h-11 w-full text-amber-700"
                disabled={busy}
                onClick={() => onSheetNc(true)}
              >
                <Gift className="size-4" />
                {t("Complimentary")} · {zeroLabel}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function RoomPicker({
  rooms,
  value,
  onChange,
  onOpen,
  placeholder,
}: {
  rooms: SettleRoom[]
  value: string
  onChange: (room: string) => void
  onOpen: () => void
  placeholder: string
}) {
  const { t } = useT()
  return (
    <select
      className={inputCls}
      value={value}
      onFocus={onOpen}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {rooms.map((r) => {
        const blocked = Number(r.room_charges_allowed ?? 1) === 0
        return (
          <option key={r.room} value={r.room} disabled={blocked}>
            {r.room_number}
            {r.guest_name ? ` · ${r.guest_name}` : ""}
            {blocked ? ` (${t("no room charges")})` : ""}
          </option>
        )
      })}
    </select>
  )
}
