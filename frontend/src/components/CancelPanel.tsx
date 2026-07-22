import { useEffect, useState } from "react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import type { Row } from "../lib/resource"
import { Button } from "./ui/button"
import { toFullPath } from "../lib/routing"

/** Cancel a stay the right way: see what it costs, say why, get a
 * cancellation number the guest can keep. Lives in the reservation
 * drawer - the status field itself refuses direct flips to Cancelled. */

const REASONS = [
  "Guest request",
  "Change of plans",
  "Duplicate booking",
  "Payment failed",
  "Weather / travel disruption",
  "Booked elsewhere",
  "Other",
]

interface Preview {
  days_before_arrival: number
  free_cancel_days: number
  inside_window: boolean
  fee_basis: string
  estimated_fee: number
}

const inr = (n: number) =>
  Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })

export default function CancelPanel({ row, reload }: { row: Row; reload: () => void }) {
  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [reason, setReason] = useState(REASONS[0])
  const [note, setNote] = useState("")
  const [waive, setWaive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<{ cancellation_number: string; fee: number } | null>(null)

  useEffect(() => {
    if (open && !preview)
      call<Preview>("kamra.api.cancellation_preview", {
        reservation: row.name,
      })
        .then(setPreview)
        .catch((e) => setError(serverError(e)))
  }, [open, preview, row.name])

  if (row.status !== "Confirmed" && !done) return null

  if (done)
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
        <p className="font-semibold">
          Cancelled - {done.cancellation_number}
        </p>
        <p className="mt-0.5">
          {done.fee > 0
            ? `Cancellation fee ₹${inr(done.fee)} posted to the folio.`
            : "No fee applied."}{" "}
          Give the guest the cancellation number.
        </p>
        <a
          href={toFullPath(`/cancelled/${encodeURIComponent(String(row.name))}`)}
          className="mt-1.5 inline-block font-medium text-emerald-900 underline"
        >
          Print / share the confirmation letter
        </a>
      </div>
    )

  return (
    <div className="border-t border-zinc-200 pt-4">
      {!open ? (
        <Button variant="outline" onClick={() => setOpen(true)}>
          Cancel this stay…
        </Button>
      ) : (
        <div className="space-y-3">
          {preview && (
            <p className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
              {preview.days_before_arrival} day
              {preview.days_before_arrival === 1 ? "" : "s"} before arrival.{" "}
              {preview.inside_window && preview.fee_basis !== "None" ? (
                <>
                  Inside the {preview.free_cancel_days}-day window - the{" "}
                  <span className="font-medium">
                    {preview.fee_basis.toLowerCase()} (₹
                    {inr(preview.estimated_fee)})
                  </span>{" "}
                  will be charged.
                </>
              ) : (
                "Outside the fee window - cancellation is free."
              )}
            </p>
          )}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-zinc-600">
              Reason
            </span>
            <select
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            >
              {REASONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <textarea
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
            placeholder="Anything worth remembering (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          {preview?.inside_window && preview.fee_basis !== "None" && (
            <label className="flex items-center gap-2 text-sm text-zinc-600">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={waive}
                onChange={(e) => setWaive(e.target.checked)}
              />
              Waive the fee (logged - manager's call)
            </label>
          )}
          <div className="flex items-center gap-2">
            <Button
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                setError(null)
                try {
                  const out = await call<{
                    cancellation_number: string
                    fee: number
                  }>("kamra.api.cancel_reservation", {
                    reservation: row.name,
                    reason,
                    note: note || undefined,
                    waive_fee: waive ? 1 : 0,
                  })
                  setDone(out)
                  reload()
                } catch (e) {
                  setError(serverError(e))
                } finally {
                  setBusy(false)
                }
              }}
            >
              {busy ? "Cancelling…" : "Confirm cancellation"}
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Keep the booking
            </Button>
          </div>
          {error && <p className="text-xs text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  )
}
