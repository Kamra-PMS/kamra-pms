import { useEffect, useState } from "react"
import { ExternalLink, Sparkles, Star } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { Button } from "./ui/button"
import { Sheet } from "./ui/sheet"
import { cn } from "../lib/utils"

/* The check-in flow: registration readiness at a glance (with the GRC a
   click away), then a room - the allocator's pick or the desk's - then
   check in. Opened from the arrivals board instead of a blind one-click. */

interface Context {
  reservation: {
    name: string
    status: string
    guest: string | null
    guest_name: string
    room_type_name: string | null
    check_in_date: string
    check_out_date: string
    adults: number
    children: number
    planned_check_in_time: string
    vip: 0 | 1
  }
  readiness: {
    phone: boolean
    email: boolean
    id_on_file: boolean
    address_on_file: boolean
    precheckin_status: string
    link_sent: boolean
  }
  room_assigned: {
    name: string
    room_number: string
    housekeeping_status: string
  } | null
  suggestion: {
    room: string
    room_number: string
    why: string
    needs_review: 0 | 1
  } | null
  rooms: { name: string; room_number: string; housekeeping_status: string }[]
}

const hkTone: Record<string, string> = {
  Clean: "text-emerald-700",
  Inspected: "text-sky-700",
  Dirty: "text-amber-700",
}

function ReadyChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2.5 py-0.5 text-xs font-medium",
        ok
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-zinc-200 bg-zinc-50 text-zinc-500",
      )}
    >
      {ok ? "✓" : "·"} {label}
    </span>
  )
}

export default function CheckInDialog(props: {
  reservation: string
  onDone: () => void
  onClose: () => void
}) {
  const [ctx, setCtx] = useState<Context | null>(null)
  const [room, setRoom] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    call<Context>("kamra.api.checkin_context", { reservation: props.reservation })
      .then((c) => {
        setCtx(c)
        setRoom(c.room_assigned?.name || c.suggestion?.room || "")
      })
      .catch((e) => setError(serverError(e)))
  }, [props.reservation])

  async function doCheckIn() {
    setBusy(true)
    setError(null)
    try {
      await call("kamra.api.check_in", {
        reservation: props.reservation,
        room: ctx?.room_assigned ? undefined : room,
      })
      props.onDone()
    } catch (e) {
      setError(serverError(e))
      setBusy(false)
    }
  }

  const r = ctx?.reservation
  const chosen =
    ctx?.room_assigned ??
    ctx?.rooms.find((x) => x.name === room) ??
    null
  const chosenDirty = chosen?.housekeeping_status === "Dirty"

  return (
    <Sheet
      title={r ? `Check in ${r.guest_name}` : "Check in"}
      description={
        r
          ? `${r.room_type_name ?? ""} · ${r.check_in_date} → ${r.check_out_date} · ${r.adults} adult${r.adults === 1 ? "" : "s"}${r.children ? ` + ${r.children}` : ""}${r.planned_check_in_time ? ` · ETA ${r.planned_check_in_time.slice(0, 5)}` : ""}`
          : undefined
      }
      onClose={props.onClose}
      footer={
        <div className="flex w-full items-center gap-3">
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" onClick={props.onClose}>
              Cancel
            </Button>
            <Button disabled={busy || !room || !ctx} onClick={doCheckIn}>
              {busy
                ? "Checking in…"
                : chosen
                  ? `Check in to ${chosen.room_number}`
                  : "Check in"}
            </Button>
          </div>
        </div>
      }
    >
      {!ctx && !error && <p className="text-sm text-zinc-500">Loading…</p>}
      {ctx && r && (
        <div className="space-y-5">
          <section>
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-zinc-700">
                Registration
              </h3>
              {r.vip ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-amber-600">
                  <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
                  VIP
                </span>
              ) : null}
              <a
                href={toFullPath(`/grc/${r.name}`)}
                target="_blank"
                rel="noreferrer"
                className="ml-auto flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
              >
                Open GRC <ExternalLink className="size-3.5" aria-hidden />
              </a>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <ReadyChip
                ok={ctx.readiness.precheckin_status === "Verified"}
                label={
                  ctx.readiness.precheckin_status === "Not Started"
                    ? ctx.readiness.link_sent
                      ? "Online check-in sent, not filled"
                      : "Online check-in not sent"
                    : `Online check-in ${ctx.readiness.precheckin_status.toLowerCase()}`
                }
              />
              <ReadyChip ok={ctx.readiness.id_on_file} label="ID on file" />
              <ReadyChip
                ok={ctx.readiness.address_on_file}
                label="Address proof"
              />
              <ReadyChip ok={ctx.readiness.phone} label="Phone" />
              <ReadyChip ok={ctx.readiness.email} label="Email" />
            </div>
            {!ctx.readiness.id_on_file && (
              <p className="mt-2 text-xs text-zinc-500">
                Capture the ID on the GRC - check-in is never blocked, but the
                register wants it before the night audit.
              </p>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-zinc-700">Room</h3>
            {ctx.room_assigned ? (
              <p className="text-sm text-zinc-700">
                Room{" "}
                <span className="font-semibold">
                  {ctx.room_assigned.room_number}
                </span>{" "}
                is assigned
                {ctx.room_assigned.housekeeping_status && (
                  <span
                    className={cn(
                      "ml-2 text-xs font-medium",
                      hkTone[ctx.room_assigned.housekeeping_status] ??
                        "text-zinc-500",
                    )}
                  >
                    {ctx.room_assigned.housekeeping_status}
                  </span>
                )}
              </p>
            ) : (
              <div className="space-y-3">
                {ctx.suggestion && (
                  <button
                    onClick={() => setRoom(ctx.suggestion!.room)}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-xl border p-3 text-left transition",
                      room === ctx.suggestion.room
                        ? "border-brand-400 bg-brand-50"
                        : "border-zinc-200 hover:border-brand-300",
                    )}
                  >
                    <Sparkles
                      className="mt-0.5 size-4 shrink-0 text-brand-600"
                      aria-hidden
                    />
                    <span className="text-sm">
                      <span className="font-semibold">
                        Room {ctx.suggestion.room_number}
                      </span>{" "}
                      <span className="text-zinc-500">— {ctx.suggestion.why}</span>
                    </span>
                  </button>
                )}
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">
                    {ctx.suggestion ? "Or pick another room" : "Pick a room"}
                  </span>
                  <select
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                    value={room}
                    onChange={(e) => setRoom(e.target.value)}
                  >
                    <option value="">Choose…</option>
                    {ctx.rooms.map((x) => (
                      <option key={x.name} value={x.name}>
                        {x.room_number} · {x.housekeeping_status}
                      </option>
                    ))}
                  </select>
                </label>
                {ctx.rooms.length === 0 && (
                  <p className="text-sm text-rose-600">
                    No free room of this type for these dates - check the tape
                    chart for a move or an upgrade.
                  </p>
                )}
                {chosenDirty && (
                  <p className="text-xs font-medium text-amber-700">
                    {chosen?.room_number} hasn't been cleaned yet - housekeeping
                    will see the room flip to occupied.
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </Sheet>
  )
}
