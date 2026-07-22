import { useEffect, useState } from "react"
import { Loader2, Megaphone, Plus, Star, Trash2, X } from "lucide-react"
import {
  call,
  createBooking,
  getBookingOptions,
  getCurrentProperty,
  getQuote,
  guestSearch,
  type BookingOptions,
  type GuestHit,
  type Quote,
} from "../lib/api"
import { Button } from "./ui/button"
import { cur, moneyLocale } from "../lib/money"

interface ExtraRoom {
  room_type: string
  adults: number
  children: number
  meal_plan: string
}

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
  n.toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

export function BookingDialog(props: {
  initial: {
    room_type?: string
    date?: string
    guest?: string
    guest_name?: string
    phone?: string
    stays?: number
  }
  onClose: () => void
  onBooked: () => void
}) {
  const [options, setOptions] = useState<BookingOptions | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  const [quoting, setQuoting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{
    ref: string
    room: string | null
    waitlist?: boolean
  } | null>(
    null,
  )

  const [form, setForm] = useState({
    guest_name: props.initial.guest_name ?? "",
    phone: props.initial.phone ?? "",
    room_type: props.initial.room_type ?? "",
    check_in_date: props.initial.date ?? new Date().toISOString().slice(0, 10),
    nights: 1,
    adults: 2,
    children: 0,
    meal_plan: "",
    voucher_code: "",
    company: "",
    travel_agent: "",
    booked_by_name: "",
    booked_by_phone: "",
    booker_relation: "",
    contact_preference: "Booker",
  })
  const [onBehalf, setOnBehalf] = useState(false)
  const [moreRooms, setMoreRooms] = useState<ExtraRoom[]>([])
  const [moreQuotes, setMoreQuotes] = useState<(Quote | null)[]>([])
  const [addonQty, setAddonQty] = useState<Record<string, number>>({})
  const [profile, setProfile] = useState<GuestHit | null>(() =>
    props.initial.guest
      ? {
          name: props.initial.guest,
          full_name: props.initial.guest_name ?? "",
          phone: props.initial.phone ?? null,
          email: null,
          vip: 0,
          blacklisted: 0,
          stays: props.initial.stays ?? 0,
          last_stay: null,
        }
      : null,
  )
  const [hits, setHits] = useState<GuestHit[]>([])

  // profile typeahead - find the returning guest before creating a dupe
  useEffect(() => {
    if (profile || form.guest_name.trim().length < 2) {
      setHits([])
      return
    }
    const t = setTimeout(
      () => guestSearch(form.guest_name).then(setHits).catch(() => setHits([])),
      250,
    )
    return () => clearTimeout(t)
  }, [form.guest_name, profile])

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

  // quotes for the additional rooms
  useEffect(() => {
    if (moreRooms.length === 0) {
      setMoreQuotes([])
      return
    }
    const t = setTimeout(() => {
      Promise.all(
        moreRooms.map((r) =>
          r.room_type
            ? getQuote({
                room_type: r.room_type,
                check_in_date: form.check_in_date,
                check_out_date: checkOut,
                adults: r.adults,
                children: r.children,
                meal_plan: r.meal_plan || undefined,
              }).catch(() => null)
            : Promise.resolve(null),
        ),
      ).then(setMoreQuotes)
    }, 300)
    return () => clearTimeout(t)
  }, [moreRooms, form.check_in_date, checkOut])

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

  async function submit(waitlist = false) {
    setBusy(true)
    setError(null)
    try {
      if (waitlist) {
        const res = await createBooking({
          guest_name: form.guest_name,
          phone: form.phone || undefined,
          guest: profile?.name,
          room_type: form.room_type,
          check_in_date: form.check_in_date,
          check_out_date: checkOut,
          adults: form.adults,
          children: form.children,
          meal_plan: form.meal_plan || undefined,
          voucher_code: form.voucher_code || undefined,
          company: form.company || undefined,
          waitlist: 1,
        })
        setDone({ ref: res.reservation, room: null, waitlist: true })
        props.onBooked()
        return
      }
      if (moreRooms.length > 0) {
        // several rooms → one group booking, billable as a block
        const rooms = [
          {
            room_type: form.room_type,
            count: 1,
            adults: form.adults,
            children: form.children,
            meal_plan: form.meal_plan || undefined,
          },
          ...moreRooms.map((r) => ({
            room_type: r.room_type,
            count: 1,
            adults: r.adults,
            children: r.children,
            meal_plan: r.meal_plan || undefined,
          })),
        ]
        const out = await call<{
          group_booking: string
          created: string[]
          skipped: { room_type: string; reason: string }[]
        }>("kamra.api.create_group_booking", {
          property: getCurrentProperty(),
          group_name: `${form.guest_name} · ${rooms.length} rooms`,
          check_in_date: form.check_in_date,
          check_out_date: checkOut,
          rooms,
          guest_name: form.guest_name,
          phone: form.phone || undefined,
          company: form.company || undefined,
        })
        if (out.skipped.length > 0) {
          setError(
            `Booked ${out.created.length} of ${rooms.length} rooms - ` +
              out.skipped.map((s) => s.reason).join("; "),
          )
          if (out.created.length === 0) return
        }
        setDone({ ref: out.group_booking, room: null })
        props.onBooked()
        return
      }
      const res = await createBooking({
        guest_name: form.guest_name,
        phone: form.phone || undefined,
        guest: profile?.name,
        room_type: form.room_type,
        check_in_date: form.check_in_date,
        check_out_date: checkOut,
        adults: form.adults,
        children: form.children,
        meal_plan: form.meal_plan || undefined,
        voucher_code: form.voucher_code || undefined,
        company: form.company || undefined,
        travel_agent: form.travel_agent || undefined,
        booking_type: form.company ? "Corporate" : undefined,
        booked_by_name: onBehalf ? form.booked_by_name || undefined : undefined,
        booked_by_phone: onBehalf
          ? form.booked_by_phone || undefined
          : undefined,
        booker_relation: onBehalf
          ? form.booker_relation || undefined
          : undefined,
        contact_preference:
          onBehalf && form.booked_by_name ? form.contact_preference : undefined,
        addons: Object.entries(addonQty)
          .filter(([, q]) => q > 0)
          .map(([experience, qty]) => ({ experience, qty })),
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

  const selectedRt = options?.room_types.find(
    (rt) => rt.name === form.room_type,
  )
  const roomTypeName = selectedRt?.room_type_name ?? ""
  const overCapacity =
    !!selectedRt &&
    ((selectedRt.adults_capacity > 0 &&
      form.adults > selectedRt.adults_capacity) ||
      (selectedRt.children_capacity > 0 &&
        form.children > selectedRt.children_capacity))

  // rooms needed to sleep the whole party in this room type, keeping at
  // least one adult in every room
  const roomsNeeded = (() => {
    if (!selectedRt) return 1
    const capA = selectedRt.adults_capacity || form.adults || 1
    const capC = selectedRt.children_capacity
    const n = Math.max(
      Math.ceil(form.adults / Math.max(1, capA)),
      capC > 0 ? Math.ceil(form.children / capC) : 1,
      1,
    )
    return Math.min(n, Math.max(1, form.adults))
  })()

  const distributeParty = () => {
    // spread the party as evenly as possible; the lot books as one group
    const n = roomsNeeded
    const baseA = Math.floor(form.adults / n)
    const remA = form.adults % n
    const baseC = Math.floor(form.children / n)
    const remC = form.children % n
    const alloc = Array.from({ length: n }, (_, i) => ({
      adults: baseA + (i < remA ? 1 : 0),
      children: baseC + (i < remC ? 1 : 0),
    }))
    setForm((f) => ({
      ...f,
      adults: alloc[0].adults,
      children: alloc[0].children,
    }))
    setMoreRooms(
      alloc.slice(1).map((a) => ({
        room_type: form.room_type,
        adults: a.adults,
        children: a.children,
        meal_plan: form.meal_plan,
      })),
    )
  }

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label="New booking"
      onKeyDown={(e) => e.key === "Escape" && props.onClose()}
    >
      <div
        className="absolute inset-0 bg-black/40 animate-fade-in"
        onClick={props.onClose}
        aria-hidden
      />
      <div className="absolute inset-y-0 right-0 w-full max-w-[64rem] overflow-y-auto bg-white shadow-2xl animate-sheet-in sm:w-[66vw]">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-100 bg-white px-7 py-5">
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
            {done.waitlist ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-800">
                <p className="text-lg font-semibold">
                  Waitlisted - {done.ref}
                </p>
                <p className="mt-1 text-sm">
                  Parked with no room. Promote it from the reservation when a
                  room frees - or let the agent watch availability and reach
                  the guest proactively. Auto-purges 2 days after departure.
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-emerald-800">
                <p className="text-lg font-semibold">Booked - {done.ref}</p>
                <p className="mt-1 text-sm">
                  {done.room
                    ? `Room ${done.room.split("-").pop()} assigned.`
                    : "No room auto-assigned - pick one from Reservations."}{" "}
                  Find it under Arrivals on the stay date.
                </p>
              </div>
            )}
            <Button className="px-5 py-2.5 text-base" onClick={props.onClose}>
              Done
            </Button>
          </div>
        ) : (
          <div className="grid gap-0 md:grid-cols-5">
            {/* form - left 3/5 */}
            <div className="space-y-5 px-7 py-6 md:col-span-3">
              {options?.property?.sell_message && (
                <div className="flex items-start gap-2 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-900">
                  <Megaphone
                    className="mt-0.5 size-4 shrink-0 text-brand-700"
                    aria-hidden
                  />
                  <span>{options.property.sell_message}</span>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <Field label="Guest name">
                  <div className="relative">
                    <input
                      className={inputCls}
                      value={form.guest_name}
                      onChange={(e) => {
                        setProfile(null)
                        set("guest_name", e.target.value)
                      }}
                      placeholder="Type to find or create"
                      autoFocus
                    />
                    {hits.length > 0 && (
                      <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-lg">
                        {hits.map((h) => (
                          <li key={h.name}>
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50"
                              onClick={() => {
                                setProfile(h)
                                setHits([])
                                setForm((f) => ({
                                  ...f,
                                  guest_name: h.full_name,
                                  phone: h.phone ?? f.phone,
                                }))
                              }}
                            >
                              <span className="font-medium">{h.full_name}</span>
                              {Boolean(h.vip) && (
                                <Star
                                  className="size-3 fill-amber-400 text-amber-400"
                                  aria-label="VIP"
                                />
                              )}
                              <span className="ml-auto text-xs text-zinc-400">
                                {h.phone ? `${h.phone} · ` : ""}
                                {h.stays} stay{h.stays === 1 ? "" : "s"}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {profile && (
                    <span className="mt-1.5 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                      Returning guest · {profile.stays} stay
                      {profile.stays === 1 ? "" : "s"}
                      <button
                        type="button"
                        aria-label="Detach profile - create a new guest instead"
                        onClick={() => setProfile(null)}
                        className="text-brand-700/60 hover:text-brand-700"
                      >
                        <X className="size-3" aria-hidden />
                      </button>
                    </span>
                  )}
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
                      {rt.room_type_name} · {cur()}{inr(rt.base_price)}/night
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

              {selectedRt &&
                (selectedRt.adults_capacity > 0 ||
                  selectedRt.children_capacity > 0) &&
                (overCapacity ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
                    {selectedRt.room_type_name} sleeps up to{" "}
                    <strong>{selectedRt.adults_capacity} adults</strong>
                    {selectedRt.children_capacity > 0 && (
                      <>
                        {" · "}
                        <strong>
                          {selectedRt.children_capacity} children
                        </strong>
                      </>
                    )}{" "}
                    per room. For a bigger party, split them across rooms —
                    it books as one group.{" "}
                    <button
                      className="font-semibold text-brand-700 hover:underline"
                      onClick={distributeParty}
                    >
                      Split into {roomsNeeded} rooms
                    </button>
                  </div>
                ) : (
                  <p className="-mt-2 text-xs text-zinc-400">
                    Sleeps up to {selectedRt.adults_capacity} adults
                    {selectedRt.children_capacity > 0 &&
                      ` · ${selectedRt.children_capacity} children`}
                  </p>
                ))}

              {/* additional rooms - books the lot as one group */}
              {moreRooms.map((r, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-end gap-2 rounded-xl border border-zinc-200 px-3 py-2.5"
                >
                  <span className="w-full text-xs font-medium uppercase tracking-wider text-zinc-400">
                    Room {i + 2}
                  </span>
                  <select
                    className={`${inputCls} !w-auto flex-1`}
                    aria-label={`Room ${i + 2} type`}
                    value={r.room_type}
                    onChange={(e) =>
                      setMoreRooms((rs) =>
                        rs.map((x, j) =>
                          j === i ? { ...x, room_type: e.target.value } : x,
                        ),
                      )
                    }
                  >
                    {options?.room_types.map((rt) => (
                      <option key={rt.name} value={rt.name}>
                        {rt.room_type_name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={1}
                    aria-label={`Room ${i + 2} adults`}
                    className={`${inputCls} !w-16`}
                    value={r.adults}
                    onChange={(e) =>
                      setMoreRooms((rs) =>
                        rs.map((x, j) =>
                          j === i
                            ? { ...x, adults: Math.max(1, Number(e.target.value)) }
                            : x,
                        ),
                      )
                    }
                  />
                  <select
                    className={`${inputCls} !w-auto`}
                    aria-label={`Room ${i + 2} meal plan`}
                    value={r.meal_plan}
                    onChange={(e) =>
                      setMoreRooms((rs) =>
                        rs.map((x, j) =>
                          j === i ? { ...x, meal_plan: e.target.value } : x,
                        ),
                      )
                    }
                  >
                    <option value="">Room only</option>
                    {options?.meal_plans.map((mp) => (
                      <option key={mp.name} value={mp.name}>
                        {mp.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="rounded p-1.5 text-zinc-400 hover:text-rose-500"
                    aria-label={`Remove room ${i + 2}`}
                    onClick={() =>
                      setMoreRooms((rs) => rs.filter((_, j) => j !== i))
                    }
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </div>
              ))}
              <button
                className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
                onClick={() =>
                  setMoreRooms((rs) => [
                    ...rs,
                    {
                      room_type: form.room_type,
                      adults: 2,
                      children: 0,
                      meal_plan: form.meal_plan,
                    },
                  ])
                }
              >
                <Plus className="size-4" aria-hidden />
                Add another room
              </button>

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
                        {mp.label} (+{cur()}{inr(mp.price_per_adult)}/adult)
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

              <div className="grid grid-cols-2 gap-4">
                <Field label="Company (bill corporate)">
                  <select
                    className={inputCls}
                    value={form.company}
                    onChange={(e) => set("company", e.target.value)}
                  >
                    <option value="">-</option>
                    {options?.companies.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.company_name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Travel agent">
                  <select
                    className={inputCls}
                    value={form.travel_agent}
                    onChange={(e) => set("travel_agent", e.target.value)}
                  >
                    <option value="">-</option>
                    {options?.travel_agents.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.agent_name} ({t.commission_pct}%)
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              {moreRooms.length === 0 &&
                (options?.experiences.length ?? 0) > 0 && (
                  <div>
                    <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                      Add-ons
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {options?.experiences.map((x) => {
                        const on = (addonQty[x.name] ?? 0) > 0
                        return (
                          <button
                            key={x.name}
                            type="button"
                            aria-pressed={on}
                            className={
                              on
                                ? "rounded-full bg-brand-600 px-3 py-1.5 text-sm font-medium text-white"
                                : "rounded-full border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 hover:border-brand-600"
                            }
                            onClick={() =>
                              setAddonQty((q) => ({
                                ...q,
                                [x.name]: on ? 0 : 1,
                              }))
                            }
                          >
                            {x.experience_name} · {cur()}{inr(x.price)}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

              {moreRooms.length > 0 && (
                <p className="text-xs text-zinc-400">
                  Multi-room bookings are created as a group - vouchers,
                  add-ons and booker details can be added per stay afterwards.
                </p>
              )}

              {moreRooms.length === 0 && (
              <div className="rounded-xl border border-zinc-200 px-4 py-3">
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-700">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={onBehalf}
                    onChange={(e) => setOnBehalf(e.target.checked)}
                  />
                  Booked on someone's behalf
                </label>
                {onBehalf && (
                  <div className="mt-3 space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <Field label="Booker name">
                        <input
                          className={inputCls}
                          value={form.booked_by_name}
                          onChange={(e) =>
                            set("booked_by_name", e.target.value)
                          }
                          placeholder="Who arranged this stay"
                        />
                      </Field>
                      <Field label="Booker phone">
                        <input
                          className={inputCls}
                          value={form.booked_by_phone}
                          onChange={(e) =>
                            set("booked_by_phone", e.target.value)
                          }
                          placeholder="+91 …"
                        />
                      </Field>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <Field label="Relation">
                        <select
                          className={inputCls}
                          value={form.booker_relation}
                          onChange={(e) =>
                            set("booker_relation", e.target.value)
                          }
                        >
                          <option value="">-</option>
                          {[
                            "Assistant",
                            "Family",
                            "Company Travel Desk",
                            "Travel Agent",
                          ].map((r) => (
                            <option key={r}>{r}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Send links & updates to">
                        <select
                          className={inputCls}
                          value={form.contact_preference}
                          onChange={(e) =>
                            set("contact_preference", e.target.value)
                          }
                        >
                          <option value="Booker">Booker</option>
                          <option value="Guest">Guest</option>
                          <option value="Both">Both</option>
                        </select>
                      </Field>
                    </div>
                  </div>
                )}
              </div>
              )}
            </div>

            {/* quote - right 2/5 */}
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
                      <span>{cur()}{inr(quote.room_total)}</span>
                    </div>
                    {quote.meal_total > 0 && (
                      <div className="flex justify-between text-zinc-600">
                        <span>Meals</span>
                        <span>{cur()}{inr(quote.meal_total)}</span>
                      </div>
                    )}
                    {quote.discount > 0 && (
                      <div className="flex justify-between font-medium text-emerald-700">
                        <span>Voucher</span>
                        <span>−{cur()}{inr(quote.discount)}</span>
                      </div>
                    )}
                    <div className="flex justify-between text-zinc-600">
                      <span>GST {quote.tax_percent}%</span>
                      <span>{cur()}{inr(quote.tax_amount)}</span>
                    </div>
                    {moreQuotes.map((mq, i) =>
                      mq ? (
                        <div
                          key={i}
                          className="flex justify-between text-zinc-600"
                        >
                          <span>
                            Room {i + 2} ·{" "}
                            {options?.room_types.find(
                              (rt) => rt.name === moreRooms[i]?.room_type,
                            )?.room_type_name ?? ""}
                          </span>
                          <span>{cur()}{inr(mq.amount_after_tax)}</span>
                        </div>
                      ) : null,
                    )}
                    {(() => {
                      const addonsGross = Object.entries(addonQty).reduce(
                        (s, [n, q]) => {
                          const x = options?.experiences.find(
                            (e) => e.name === n,
                          )
                          return x && q > 0
                            ? s + q * x.price * (1 + x.gst_rate / 100)
                            : s
                        },
                        0,
                      )
                      const grand =
                        quote.amount_after_tax +
                        moreQuotes.reduce(
                          (s, q) => s + (q?.amount_after_tax ?? 0),
                          0,
                        ) +
                        addonsGross
                      const pol = options?.property
                      const cutoff = (() => {
                        if (!pol) return ""
                        const d = new Date(form.check_in_date + "T00:00:00")
                        d.setDate(d.getDate() - (pol.free_cancel_days || 0))
                        return d.toISOString().slice(0, 10)
                      })()
                      return (
                        <>
                          {addonsGross > 0 && (
                            <div className="flex justify-between text-zinc-600">
                              <span>Add-ons (incl. GST)</span>
                              <span>{cur()}{inr(addonsGross)}</span>
                            </div>
                          )}
                          <div className="mt-2 flex items-baseline justify-between border-t border-zinc-200 pt-3">
                            <span className="text-sm font-medium text-zinc-500">
                              Total{moreRooms.length > 0 ? " · all rooms" : ""}
                            </span>
                            <span className="text-2xl font-semibold">
                              {cur()}{inr(grand)}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400">
                            {form.check_in_date} → {checkOut}
                          </p>
                          {pol && (
                            <p className="mt-2 border-t border-zinc-200 pt-2 text-xs leading-relaxed text-zinc-500">
                              {pol.cancellation_fee === "None"
                                ? "Free cancellation."
                                : `Free cancellation until ${cutoff}; after that the ${pol.cancellation_fee.toLowerCase()} is charged.`}
                              {pol.no_show_charge !== "None" &&
                                ` No-show: ${pol.no_show_charge.toLowerCase()} charged.`}
                              {pol.deposit_pct > 0 &&
                                ` Deposit expected now: ${cur()}${inr((grand * pol.deposit_pct) / 100)} (${pol.deposit_pct}%).`}
                            </p>
                          )}
                        </>
                      )
                    })()}
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
                  className="justify-center py-2.5 text-base"
                  onClick={props.onClose}
                >
                  Cancel
                </Button>
                <Button
                  variant="outline"
                  className="justify-center py-2.5 text-base"
                  disabled={busy || !form.guest_name}
                  onClick={() => submit(true)}
                  title="Park this stay with no room (sold out / restricted dates); promote it when a room frees"
                >
                  Add to waitlist
                </Button>
                <Button
                  className="flex-1 justify-center py-2.5 text-base"
                  disabled={busy || !form.guest_name || !quote}
                  onClick={() => submit()}
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
