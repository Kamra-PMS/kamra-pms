import { useEffect, useState } from "react"
import { Check, Shirt, Zap } from "lucide-react"
import { call } from "../../lib/api"
import { Button } from "../../components/ui/button"
import { inr, type Rate } from "./shared"

/** In-stay guest self-service: request a laundry pickup from the check-in page.
 * Read-only price list + a request button. The guest never sees a folio or a
 * total — staff count and price the bag at the door. Written on the guest's
 * behalf by the governed agent (kamra.public_api.request_guest_laundry). */

interface LaundryInfo {
  room_no: string
  rates: Rate[]
  has_open_order: boolean
}

export function GuestLaundryCard({ token }: Readonly<{ token: string }>) {
  const [info, setInfo] = useState<LaundryInfo | null>(null)
  const [open, setOpen] = useState(false)
  const [showRates, setShowRates] = useState(false)
  const [express, setExpress] = useState(false)
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const [requested, setRequested] = useState(false)

  useEffect(() => {
    if (!token) return
    call<LaundryInfo>("kamra.public_api.laundry_info", { token })
      .then(setInfo)
      .catch(() => setInfo(null)) // not checked in / no rate card → hide
  }, [token])

  if (!info || info.rates.length === 0) return null

  const alreadyOpen = info.has_open_order || requested

  async function submit() {
    setBusy(true)
    try {
      await call("kamra.public_api.request_guest_laundry", {
        token,
        notes: notes || "",
        express: express ? 1 : 0,
      })
      setRequested(true)
      setOpen(false)
    } catch {
      // surfaced by the disabled state; keep the sheet open to retry
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-5 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <Shirt className="size-5 text-brand-600" aria-hidden />
        <p className="font-medium">Laundry</p>
      </div>

      {alreadyOpen ? (
        <p className="mt-2 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          <Check className="size-4" aria-hidden />
          Housekeeping has your laundry pickup — they'll be by shortly.
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-zinc-500">
            Need clothes washed? Ask housekeeping to pick them up — they'll
            count and price the bag with you at the door.
          </p>

          {!open ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => setOpen(true)}>Request pickup</Button>
              <Button
                variant="ghost"
                onClick={() => setShowRates((s) => !s)}
              >
                {showRates ? "Hide prices" : "See prices"}
              </Button>
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <input
                className="w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                placeholder="Anything we should know? (bag by the door, after 3pm…)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <button
                type="button"
                className={
                  "flex w-full items-center justify-center gap-1.5 rounded-lg border py-2.5 text-sm font-semibold " +
                  (express
                    ? "border-amber-400 bg-amber-50 text-amber-700"
                    : "border-zinc-300 text-zinc-500")
                }
                onClick={() => setExpress((v) => !v)}
              >
                <Zap className="size-4" aria-hidden />
                {express
                  ? "Express — same day (higher rate)"
                  : "Standard service"}
              </button>
              <div className="flex gap-2">
                <Button className="flex-1" disabled={busy} onClick={submit}>
                  Send request
                </Button>
                <Button variant="ghost" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {showRates && (
            <div className="mt-3 max-h-56 overflow-y-auto rounded-lg border border-zinc-100">
              <table className="w-full text-sm">
                <tbody>
                  {info.rates.map((r) => (
                    <tr
                      key={`${r.item_name}-${r.service_type}`}
                      className="border-b border-zinc-100 last:border-0"
                    >
                      <td className="px-3 py-1.5 font-medium">{r.item_name}</td>
                      <td className="px-2 py-1.5 text-zinc-500">
                        {r.service_type}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums">
                        ₹{inr(r.rate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
