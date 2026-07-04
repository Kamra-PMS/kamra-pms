import { useEffect, useState } from "react"
import { Loader2, X } from "lucide-react"
import {
  createBooking,
  getBookingOptions,
  getQuote,
  type BookingOptions,
  type Quote,
} from "../lib/api"
import { Button } from "./ui/button"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-zinc-600">
        {props.label}
      </span>
      {props.children}
    </label>
  )
}

const inr = (n: number) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: 0 })

export function BookingDialog(props: {
  initial: { room_type?: string; date?: string }
  onClose: () => void
  onBooked: () => void
}) {
  const [options, setOptions] = useState<BookingOptions | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ ref: string; room: string | null } | null>(
    null,
  )

  const [form, setForm] = useState({
    guest_name: "",
    phone: "",
    room_type: props.initial.room_type ?? "",
    check_in_date: props.initial.date ?? new Date().toISOString().slice(0, 10),
    nights: 1,
    adults: 2,
    children: 0,
    meal_plan: "",
    voucher_code: "",
  })

  useEffect(() => {
    getBookingOptions().then((o) => {
      setOptions(o)
      setForm((f) => ({
        ...f,
        room_type: f.room_type || o.room_types[0]?.name || "",
        meal_plan: o.meal_plans.find((m) => m.is_default)?.name ?? "",
      }))
    })
  }, [])

  const checkOut = (() => {
    const d = new Date(form.check_in_date)
    d.setDate(d.getDate() + Math.max(1, form.nights))
    return d.toISOString().slice(0, 10)
  })()

  useEffect(() => {
    if (!form.room_type) return
    setQuoting(true)
    const t = setTimeout(() => {
      getQuote({
        room_type: form.room_type,
        check_in_date: form.check_in_date,
        check_out_date: checkOut,
        adults: form.adults,
        children: form.children,
        meal_plan: form.meal_plan || undefined,
        voucher_code: form.voucher_code || undefined,
      })
        .then((q) => {
          setQuote(q)
          setError(null)
        })
        .catch((e) => {
          setQuote(null)
          setError(shortErr(e))
        })
        .finally(() => setQuoting(false))
    }, 300)
    return () => clearTimeout(t)
  }, [
    form.room_type,
    form.check_in_date,
    form.nights,
    form.adults,
    form.children,
    form.meal_plan,
    form.voucher_code,
    checkOut,
  ])

  function shortErr(e: unknown): string {
    const body = (e as { body?: string }).body
    if (body) {
      try {
        const msgs = JSON.parse(JSON.parse(body)._server_messages ?? "[]")
        if (msgs.length)
          return String(JSON.parse(msgs[0]).message).replace(/<[^>]+>/g, "")
      } catch {
        /* fall through */
      }
    }
    return (e as Error).message
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const res = await createBooking({
        guest_name: form.guest_name,
        phone: form.phone || undefined,
        room_type: form.room_type,
        check_in_date: form.check_in_date,
        check_out_date: checkOut,
        adults: form.adults,
        children: form.children,
        meal_plan: form.meal_plan || undefined,
        voucher_code: form.voucher_code || undefined,
      })
      setDone({ ref: res.reservation, room: res.room })
      props.onBooked()
    } catch (e) {
      setError(shortErr(e))
    } finally {
      setBusy(false)
    }
  }

  const set = (k: string, v: string | number) =>
    setForm((f) => ({ ...f, [k]: v }))

  const roomTypeName =
    options?.room_types.find((rt) => rt.name === form.room_type)
      ?.room_type_name ?? ""

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="New booking"
      onKeyDown={(e) => e.key === "Escape" && props.onClose()}
    >
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-100 px-7 py-5">
          <div>
            <h2 className="text-xl font-semibold">New booking</h2>
            <p className="mt-0.5 text-sm text-zinc-400">
              Kamra Demo Palace · quote updates as you type
            </p>
          </div>
          <Button variant="ghost" onClick={props.onClose} aria-label="Close">
            <X className="size-5" />
          </Button>
        </div>

        {done ? (
          <div className="space-y-5 px-7 py-8">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-emerald-800">
              <p className="text-lg font-semibold">Booked — {done.ref}</p>
              <p className="mt-1 text-sm">
                {done.room
                  ? `Room ${done.room.split("-").pop()} assigned.`
                  : "No room auto-assigned — pick one from Reservations."}{" "}
                Find it under Arrivals on the stay date.
              </p>
            </div>
            <Button className="px-5 py-2.5 text-base" onClick={props.onClose}>
              Done
            </Button>
          </div>
        ) : (
          <div className="grid gap-0 md:grid-cols-5">
            {/* form — left 3/5 */}
            <div className="space-y-5 px-7 py-6 md:col-span-3">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Guest name">
                  <input
                    className={inputCls}
                    value={form.guest_name}
                    onChange={(e) => set("guest_name", e.target.value)}
                    placeholder="Full name"
                    autoFocus
                  />
                </Field>
                <Field label="Phone">
                  <input
                    className={inputCls}
                    value={form.phone}
                    onChange={(e) => set("phone", e.target.value)}
                    placeholder="+91 …"
                  />
                </Field>
              </div>

              <Field label="Room type">
                <select
                  className={inputCls}
                  value={form.room_type}
                  onChange={(e) => set("room_type", e.target.value)}
                >
                  {options?.room_types.map((rt) => (
                    <option key={rt.name} value={rt.name}>
                      {rt.room_type_name} · ₹{inr(rt.base_price)}/night
                    </option>
                  ))}
                </select>
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Check-in">
                  <input
                    type="date"
                    className={inputCls}
                    value={form.check_in_date}
                    onChange={(e) => set("check_in_date", e.target.value)}
                  />
                </Field>
                <Field label="Nights">
                  <input
                    type="number"
                    min={1}
                    className={inputCls}
                    value={form.nights}
                    onChange={(e) =>
                      set("nights", Math.max(1, Number(e.target.value)))
                    }
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Adults">
                  <input
                    type="number"
                    min={1}
                    className={inputCls}
                    value={form.adults}
                    onChange={(e) =>
                      set("adults", Math.max(1, Number(e.target.value)))
                    }
                  />
                </Field>
                <Field label="Children">
                  <input
                    type="number"
                    min={0}
                    className={inputCls}
                    value={form.children}
                    onChange={(e) =>
                      set("children", Math.max(0, Number(e.target.value)))
                    }
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Meal plan">
                  <select
                    className={inputCls}
                    value={form.meal_plan}
                    onChange={(e) => set("meal_plan", e.target.value)}
                  >
                    <option value="">Room only</option>
                    {options?.meal_plans.map((mp) => (
                      <option key={mp.name} value={mp.name}>
                        {mp.label} (+₹{inr(mp.price_per_adult)}/adult)
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Voucher (optional)">
                  <input
                    className={inputCls}
                    value={form.voucher_code}
                    onChange={(e) =>
                      set("voucher_code", e.target.value.toUpperCase())
                    }
                    placeholder="WELCOME10"
                  />
                </Field>
              </div>
            </div>

            {/* quote — right 2/5 */}
            <div className="flex flex-col justify-between border-t border-zinc-100 bg-zinc-50 px-7 py-6 md:col-span-2 md:border-l md:border-t-0">
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
                    Quote
                  </h3>
                  {quoting && (
                    <Loader2
                      className="size-4 animate-spin text-zinc-400"
                      aria-label="Updating quote"
                    />
                  )}
                </div>
                {quote ? (
                  <div className="space-y-2.5 text-[15px]">
                    <div className="flex justify-between text-zinc-600">
                      <span>
                        {roomTypeName} · {quote.nights} night
                        {quote.nights === 1 ? "" : "s"}
                      </span>
                      <span>₹{inr(quote.room_total)}</span>
                    </div>
                    {quote.meal_total > 0 && (
                      <div className="flex justify-between text-zinc-600">
                        <span>Meals</span>
                        <span>₹{inr(quote.meal_total)}</span>
                      </div>
                    )}
                    {quote.discount > 0 && (
                      <div className="flex justify-between font-medium text-emerald-700">
                        <span>Voucher</span>
                        <span>−₹{inr(quote.discount)}</span>
                      </div>
                    )}
                    <div className="flex justify-between text-zinc-600">
                      <span>GST {quote.tax_percent}%</span>
                      <span>₹{inr(quote.tax_amount)}</span>
                    </div>
                    <div className="mt-2 flex items-baseline justify-between border-t border-zinc-200 pt-3">
                      <span className="text-sm font-medium text-zinc-500">
                        Total
                      </span>
                      <span className="text-2xl font-semibold">
                        ₹{inr(quote.amount_after_tax)}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400">
                      {form.check_in_date} → {checkOut}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-zinc-400">
                    {error ? "Fix the issue below to see a price." : "…"}
                  </p>
                )}

                {error && (
                  <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">
                    {error}
                  </div>
                )}
              </div>

              <div className="mt-6 flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1 justify-center py-2.5 text-base"
                  onClick={props.onClose}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1 justify-center py-2.5 text-base"
                  disabled={busy || !form.guest_name || !quote}
                  onClick={submit}
                >
                  {busy ? "Booking…" : "Confirm"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
