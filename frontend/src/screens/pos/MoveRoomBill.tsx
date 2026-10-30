/*  A bill charged to the wrong room, moved to the right one the same
    business day (kamra.pos.move_room_bill). The charge leaves the first
    guest's folio and lands on the right guest's, by the room-service
    billing rules. */

import { useState } from "react"
import { BedDouble, X } from "lucide-react"
import { call } from "../../lib/api"
import { serverError } from "../../lib/resource"
import { useCashierAuth } from "../../lib/cashierAuth"
import { useT } from "../../lib/i18n"
import { Button } from "../../components/ui/button"

export default function MoveRoomBill({ order, currentRoom, rooms, onMoved }: {
  order: string
  currentRoom: string | null
  rooms: { room: string; room_number: string; guest_name: string | null; room_charges_allowed?: 0 | 1 }[]
  onMoved: () => void
}) {
  const { t } = useT()
  const { ensureUnlocked } = useCashierAuth()
  const [open, setOpen] = useState(false)
  const [room, setRoom] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function move() {
    setBusy(true)
    setErr(null)
    try {
      await ensureUnlocked()
      await call("kamra.pos.move_room_bill", { order, room, reason })
      setOpen(false)
      onMoved()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} title={t("Wrong room? Move this bill")}
        className="rounded-md border border-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 hover:border-brand-400 hover:text-brand-700">
        <BedDouble className="mr-0.5 inline size-3" aria-hidden />{t("Move to room")}
      </button>
    )
  }
  const choices = rooms.filter((r) => r.room !== currentRoom && r.room_charges_allowed !== 0)
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-3" role="dialog" aria-modal="true"
      aria-label={t("Move the bill to another room")}>
      <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} aria-hidden />
      <div className="relative z-10 w-full max-w-sm space-y-3 rounded-2xl bg-white p-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-800">{t("Move the bill to another room")}</h2>
          <button type="button" onClick={() => setOpen(false)} aria-label={t("Close")}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"><X className="size-4" /></button>
        </div>
        <p className="text-xs text-zinc-500">
          {t("For a bill posted to the wrong room today. It leaves that guest's bill and goes on the right one.")}
        </p>
        <select className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" value={room}
          onChange={(e) => setRoom(e.target.value)} aria-label={t("Right room")}>
          <option value="">{t("Right room…")}</option>
          {choices.map((r) => (
            <option key={r.room} value={r.room}>{r.room_number}{r.guest_name ? ` · ${r.guest_name}` : ""}</option>
          ))}
        </select>
        <input className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" value={reason}
          onChange={(e) => setReason(e.target.value)} placeholder={t("Why (e.g. guest gave the wrong room number)")} />
        {err && <p className="text-xs font-medium text-rose-700">{err}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>{t("Cancel")}</Button>
          <Button onClick={() => void move()} disabled={busy || !room || !reason.trim()}>{t("Move bill")}</Button>
        </div>
      </div>
    </div>
  )
}
