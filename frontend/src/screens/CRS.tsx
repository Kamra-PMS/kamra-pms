import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Search, BedDouble, MapPin, Loader2, Plus, X, Printer, ExternalLink } from "lucide-react"
import { call, newIdempotencyKey, setCurrentProperty } from "../lib/api"
import { toFullPath } from "../lib/routing"
import { Badge } from "../components/ui/badge"
import { serverError } from "../lib/resource"
import { Card, CardContent } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cur, moneyLocale, useLocale } from "../lib/money"
import { useT, t as translate } from "../lib/i18n"
import { useCashierAuth } from "../lib/cashierAuth"


const inr = (n: unknown) =>
  Number(n ?? 0).toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface RoomTypeAvail {
  room_type: string
  room_type_name: string
  available: number
  adults_capacity: number
  total: number
  per_night: number
}
interface PropAvail {
  property: string
  property_name: string
  city: string
  available_rooms: number
  from_rate: number
  room_types: RoomTypeAvail[]
}
interface Results {
  check_in_date: string
  check_out_date: string
  nights: number
  adults: number
  children: number
  properties: PropAvail[]
}

/** A trip across properties: ordinary reservations (legs) under one ITN
 * reference. Legs are priced and booked by the server, one per property. */
interface TripLeg {
  property: string
  property_name: string
  room_type: string
  room_type_name: string
  check_in_date: string
  check_out_date: string
}
interface QuotedLeg extends TripLeg {
  nights: number
  available: number
  amount_after_tax: number
  currency_symbol: string
  advance_percent: number
  advance_due: number
}
interface ItineraryLeg extends QuotedLeg {
  reservation: string
  city: string | null
  room: string | null
  status: string
  advance_paid: number
  advance_required: number
  deposit_due: number
  cancellation_number: string | null
  cancellation_fee: number
}
export interface Itinerary {
  name: string
  guest_name: string
  phone: string | null
  email: string | null
  status: string
  check_in_date: string | null
  check_out_date: string | null
  created: string
  legs: ItineraryLeg[]
  total: number | null
  advance_paid: number | null
  advance_required: number | null
  advance_due: number | null
}
interface AdvancePlan {
  amount: number
  currency_symbol: string
  advance_due: number
  unpaid: number
  legs: { reservation: string; property_name: string; check_in_date: string;
    advance_percent: number; advance_due: number; share: number }[]
}
interface TripRow {
  name: string
  guest_name: string
  status: string
  legs: { reservation: string; property: string; check_in_date: string; check_out_date: string; status: string }[]
}
interface CancelPreview {
  legs: { reservation: string; property: string; estimated_fee: number; fee_basis: string; currency_symbol: string }[]
  not_cancellable: { reservation: string; status: string }[]
  total_fee: number | null
}

const STATUS_TONE: Record<string, "green" | "sky" | "zinc" | "rose"> = {
  Booked: "green", "In stay": "sky", Completed: "zinc", Cancelled: "rose",
  Confirmed: "green", "Checked In": "sky", "Checked Out": "zinc",
}

// spelled out so the catalog extractor sees each label
const statusLabel = (s: string) => ({
  Booked: translate("Booked"), "In stay": translate("In stay"),
  Completed: translate("Completed"), Cancelled: translate("Cancelled"),
}[s] ?? translate(s))

/** Open a leg in Reservations at its own property (deposit, dates, cancel). */
function openLeg(property: string, reservation: string) {
  setCurrentProperty(property)
  window.location.assign(toFullPath(`/reservations?q=${encodeURIComponent(reservation)}`))
}

function isoToday() {
  return new Date().toISOString().slice(0, 10)
}
function plusDays(iso: string, n: number) {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

export default function CRS() {
  const { t, tn } = useT()
  const [checkIn, setCheckIn] = useState(isoToday())
  const [nights, setNights] = useState(1)
  const [adults, setAdults] = useState(2)
  const [children, setChildren] = useState(0)
  const [data, setData] = useState<Results | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [booking, setBooking] = useState<{
    property: string
    property_name: string
    rt: RoomTypeAvail
  } | null>(null)
  const [guest, setGuest] = useState({ name: "", phone: "" })
  const [done, setDone] = useState<string | null>(null)
  const [trip, setTrip] = useState<TripLeg[]>([])
  const [tripQuote, setTripQuote] = useState<{ legs: QuotedLeg[]; total: number | null; advance_due: number | null } | null>(null)
  const [traveller, setTraveller] = useState({ name: "", phone: "" })
  const [trips, setTrips] = useState<TripRow[]>([])
  const [tripSearch, setTripSearch] = useState("")
  const [openTrip, setOpenTrip] = useState<string | null>(null)

  const checkOut = plusDays(checkIn, Math.max(1, nights))

  const loadTrips = () =>
    call<TripRow[]>("kamra.crs.list_itineraries", { search: tripSearch || null })
      .then(setTrips)
      .catch(() => setTrips([]))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadTrips() }, [])

  // the server prices the whole trip each time a stop changes
  useEffect(() => {
    if (!trip.length) { setTripQuote(null); return }
    call<{ legs: QuotedLeg[]; total: number | null; advance_due: number | null }>("kamra.crs.quote_itinerary", {
      legs: trip, adults, children,
    }).then(setTripQuote).catch((e) => { setTripQuote(null); setError(serverError(e)) })
  }, [trip, adults, children])

  function addToTrip(p: PropAvail, rt: RoomTypeAvail) {
    setError(null)
    setTrip([...trip, {
      property: p.property, property_name: p.property_name,
      room_type: rt.room_type, room_type_name: rt.room_type_name,
      check_in_date: checkIn, check_out_date: checkOut,
    }])
    // the next stop starts the day this one ends
    setCheckIn(checkOut)
    setData(null)
  }

  async function bookTrip() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<Itinerary>("kamra.crs.create_itinerary", {
        legs: trip, guest_name: traveller.name, phone: traveller.phone || null,
        adults, children,
      })
      setDone(t("Trip {ref} booked: {n} stays.", { ref: r.name, n: r.legs.length }))
      setTrip([])
      setTraveller({ name: "", phone: "" })
      setOpenTrip(r.name)
      loadTrips()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function search() {
    setBusy(true)
    setError(null)
    try {
      const r = await call<Results>("kamra.crs.crs_search", {
        check_in_date: checkIn,
        check_out_date: checkOut,
        adults,
        children,
      })
      setData(r)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function book() {
    if (!booking) return
    setBusy(true)
    setError(null)
    try {
      const r = await call<{ reservation: string }>("kamra.api.create_booking", {
        property: booking.property,
        room_type: booking.rt.room_type,
        check_in_date: checkIn,
        check_out_date: checkOut,
        guest_name: guest.name,
        phone: guest.phone || null,
        adults,
        children,
        source: "Manual",
      })
      setDone(t("Booked {ref} at {property}.", { ref: r.reservation, property: booking.property_name }))
      setData(null)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-zinc-800">{t("Central reservations")}</h1>
        <p className="text-xs text-zinc-500">
          {t("Find a room across every property you manage, and book into whichever has space.")}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-5">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Check-in")}</span>
            <input type="date" className={inputCls} value={checkIn}
              onChange={(e) => setCheckIn(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Nights")}</span>
            <input type="number" min={1} className={inputCls} value={nights}
              onChange={(e) => setNights(Math.max(1, Number(e.target.value)))} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Adults")}</span>
            <input type="number" min={1} className={inputCls} value={adults}
              onChange={(e) => setAdults(Math.max(1, Number(e.target.value)))} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Children")}</span>
            <input type="number" min={0} className={inputCls} value={children}
              onChange={(e) => setChildren(Math.max(0, Number(e.target.value)))} />
          </label>
          <div className="flex items-end">
            <Button className="w-full" disabled={busy} onClick={search}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              {t("Search")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {translate(error)}
        </div>
      )}
      {done && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {done}
        </div>
      )}

      {trip.length > 0 && (
        <Card className="border-brand-200">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-zinc-800">{t("New trip")}</h2>
              <span className="text-xs text-zinc-500">{t("Search the next stop, then add it.")}</span>
            </div>
            <ol className="space-y-1.5">
              {trip.map((leg, i) => {
                const q = tripQuote?.legs.find((x) =>
                  x.property === leg.property && x.check_in_date === leg.check_in_date)
                return (
                  <li key={i} className="flex flex-wrap items-center gap-2 rounded-lg bg-zinc-50 px-3 py-2 text-sm">
                    <span className="flex size-5 items-center justify-center rounded-full bg-brand-600 text-[11px] font-semibold text-white">{i + 1}</span>
                    <span className="font-medium">{leg.property_name}</span>
                    <span className="text-zinc-500">{leg.room_type_name} · {leg.check_in_date} → {leg.check_out_date}</span>
                    {q && q.available < 1 && <Badge tone="rose">{t("No room free")}</Badge>}
                    <span className="ml-auto font-medium">{q ? `${q.currency_symbol}${inr(q.amount_after_tax)}` : "…"}</span>
                    <Button variant="ghost" aria-label={t("Remove stay")}
                      onClick={() => setTrip(trip.filter((_, j) => j !== i))}>
                      <X className="size-4" />
                    </Button>
                  </li>
                )
              })}
            </ol>
            <div className="flex justify-between border-t border-zinc-100 pt-2 text-sm font-semibold">
              <span>{t("Trip total, taxes in")}</span>
              <span>
                {tripQuote?.total != null
                  ? `${tripQuote.legs[0]?.currency_symbol ?? ""}${inr(tripQuote.total)}`
                  : tripQuote ? t("Each stay is billed in its own currency") : "…"}
              </span>
            </div>
            {(tripQuote?.advance_due ?? 0) > 0 && (
              <div className="flex justify-between text-sm text-zinc-600">
                <span>{t("Advance due at booking ({pcts})", {
                  pcts: tripQuote!.legs.map((l) => `${l.advance_percent}%`).join(", ") })}</span>
                <span>{`${tripQuote!.legs[0]?.currency_symbol ?? ""}${inr(tripQuote!.advance_due)}`}</span>
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-3">
              <input className={inputCls} placeholder={t("Guest name")} value={traveller.name}
                onChange={(e) => setTraveller({ ...traveller, name: e.target.value })} />
              <input className={inputCls} placeholder={t("Phone")} value={traveller.phone}
                onChange={(e) => setTraveller({ ...traveller, phone: e.target.value })} />
              <Button disabled={busy || !traveller.name.trim() || !tripQuote} onClick={bookTrip}>
                {t("Book trip")}
              </Button>
            </div>
            <p className="text-xs text-zinc-500">
              {t("Each stay becomes a normal booking at its own property, with its own bill. Take one advance for the trip from its sheet, or on each stay.")}
            </p>
          </CardContent>
        </Card>
      )}

      {data && (
        <div className="space-y-3">
          <p className="text-sm text-zinc-500">
            {tn(data.properties.length, "{n} property with space", "{n} properties with space")} ·{" "}
            {tn(data.nights, "{n} night", "{n} nights")}, {tn(data.adults, "{n} adult", "{n} adults")}
            {data.children ? `, ${tn(data.children, "{n} child", "{n} children")}` : ""}
          </p>
          {data.properties.length === 0 && (
            <Card><CardContent className="p-8 text-center text-sm text-zinc-400">
              {t("No rooms across the chain for these dates and party.")}
            </CardContent></Card>
          )}
          {data.properties.map((p) => (
            <Card key={p.property}>
              <CardContent className="p-4">
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <span className="text-base font-semibold text-zinc-800">{p.property_name}</span>
                    <span className="ml-2 inline-flex items-center gap-1 text-xs text-zinc-400">
                      <MapPin className="size-3" />{p.city}
                    </span>
                  </div>
                  <span className="text-xs text-zinc-500">
                    {t("{n} rooms · from {rate}/night", {
                      n: p.available_rooms,
                      rate: `${cur()}${inr(p.from_rate)}`,
                    })}
                  </span>
                </div>
                <div className="divide-y divide-zinc-100">
                  {p.room_types.map((rt) => (
                    <div key={rt.room_type} className="flex flex-wrap items-center gap-3 py-2.5">
                      <BedDouble className="size-4 shrink-0 text-zinc-400" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-zinc-800">{rt.room_type_name}</div>
                        <div className="text-xs text-zinc-500">
                          {t("{avail} left · sleeps {cap} · {rate}/night", {
                            avail: rt.available,
                            cap: rt.adults_capacity,
                            rate: `${cur()}${inr(rt.per_night)}`,
                          })}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold">{cur()}{inr(rt.total)}</div>
                        <div className="text-[11px] text-zinc-400">{t("total, taxes in")}</div>
                      </div>
                      <Button variant="outline"
                        onClick={() => { setBooking({ property: p.property, property_name: p.property_name, rt }); setGuest({ name: "", phone: "" }) }}>
                        {t("Book")}
                      </Button>
                      <Button variant="ghost" title={t("Add this stay to a trip across properties")}
                        onClick={() => addToTrip(p, rt)}>
                        <Plus className="size-4" />{t("Add to trip")}
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-zinc-800">{t("Trips")}</h2>
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); loadTrips() }}>
              <input className={inputCls} placeholder={t("Guest or ITN reference")} value={tripSearch}
                onChange={(e) => setTripSearch(e.target.value)} />
              <Button variant="outline" type="submit" aria-label={t("Search")}><Search className="size-4" /></Button>
            </form>
          </div>
          {trips.length === 0 && (
            <p className="py-4 text-center text-sm text-zinc-400">{t("No trips yet. Add stays from the search above.")}</p>
          )}
          <div className="divide-y divide-zinc-100">
            {trips.map((r) => (
              <button key={r.name} onClick={() => setOpenTrip(r.name)}
                className="flex w-full flex-wrap items-center gap-2 py-2.5 text-left text-sm hover:bg-zinc-50">
                <span className="font-mono text-xs text-zinc-500">{r.name}</span>
                <span className="font-medium text-zinc-800">{r.guest_name}</span>
                <span className="text-xs text-zinc-500">
                  {r.legs.map((l) => l.property).join(" → ")}
                  {r.legs.length > 0 && ` · ${r.legs[0].check_in_date} → ${r.legs[r.legs.length - 1].check_out_date}`}
                </span>
                <Badge className="ml-auto" tone={STATUS_TONE[r.status] ?? "zinc"}>{statusLabel(r.status)}</Badge>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {openTrip && (
        <TripSheet name={openTrip} onClose={() => setOpenTrip(null)} onChanged={loadTrips} />
      )}

      {booking && (
        <Sheet
          title={t("Book {type}", { type: booking.rt.room_type_name })}
          description={(`${booking.property_name} · ${checkIn} → ${checkOut} · ${cur()}${inr(booking.rt.total)} ${t("total")}`)}
          onClose={() => setBooking(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setBooking(null)}>{t("Cancel")}</Button>
              <Button disabled={busy || !guest.name.trim()} onClick={() => book().then(() => setBooking(null))}>
                {t("Confirm booking")}
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Guest name")}</span>
              <input className={inputCls} value={guest.name} autoFocus
                onChange={(e) => setGuest({ ...guest, name: e.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-zinc-600">{t("Phone")}</span>
              <input className={inputCls} value={guest.phone} placeholder="+91 …"
                onChange={(e) => setGuest({ ...guest, phone: e.target.value })} />
            </label>
          </div>
        </Sheet>
      )}
    </div>
  )
}


const REASONS = ["Guest request", "Change of plans", "Duplicate booking",
  "Payment failed", "Weather / travel disruption", "Booked elsewhere", "Other"]

/** One trip: legs in date order with their status and money, the
 * confirmation to print, and cancelling the whole trip. A single stay is
 * changed, paid or cancelled from its own reservation. */
function TripSheet({ name, onClose, onChanged }: { name: string; onClose: () => void; onChanged: () => void }) {
  const { t } = useT()
  const [d, setD] = useState<Itinerary | null>(null)
  const [preview, setPreview] = useState<CancelPreview | null>(null)
  const [reason, setReason] = useState(REASONS[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loc = useLocale()
  const { ensureUnlocked } = useCashierAuth()
  const [adv, setAdv] = useState<{ amount: string; mode: string; plan: AdvancePlan | null; key: string } | null>(null)

  const load = () => call<Itinerary>("kamra.crs.get_itinerary", { itinerary: name })
    .then(setD).catch((e) => setError(serverError(e)))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [name])

  async function askCancel() {
    setError(null)
    try {
      setPreview(await call<CancelPreview>("kamra.crs.cancel_itinerary_preview", { itinerary: name }))
    } catch (e) { setError(serverError(e)) }
  }
  async function cancelTrip() {
    setBusy(true)
    setError(null)
    try {
      setD(await call<Itinerary>("kamra.crs.cancel_itinerary", { itinerary: name, reason }))
      setPreview(null)
      onChanged()
    } catch (e) { setError(serverError(e)) } finally { setBusy(false) }
  }

  async function planAdvance(amount?: string) {
    setError(null)
    try {
      const plan = await call<AdvancePlan>("kamra.crs.trip_advance_preview", {
        itinerary: name, ...(amount ? { amount: Number(amount) } : {}) })
      setAdv({ amount: amount ?? String(plan.amount), mode: adv?.mode ?? loc.payment_modes[0] ?? "Cash", plan,
        // one key per "Take advance": a retry after a lost response replays
        key: adv?.key ?? newIdempotencyKey() })
    } catch (e) {
      setError(serverError(e))
      if (adv) setAdv({ ...adv, plan: null })
    }
  }
  async function takeAdvance() {
    if (!adv?.plan) return
    setBusy(true)
    setError(null)
    try {
      // money action: the till's cashier PIN, as on a single booking's deposit
      await ensureUnlocked()
      setD(await call<Itinerary>("kamra.crs.record_trip_advance", {
        itinerary: name, amount: adv.plan.amount, mode: adv.mode, idempotency_key: adv.key }))
      setAdv(null)
      onChanged()
    } catch (e) { setError(serverError(e)) } finally { setBusy(false) }
  }

  const sym = d?.legs[0]?.currency_symbol ?? ""
  const canAdvance = d?.legs.some((l) => ["Confirmed", "Pending Payment", "Held"].includes(l.status))
  const cancellable = d?.legs.some((l) => l.status === "Confirmed")
  return (
    <Sheet wide title={t("Trip {ref}", { ref: name })}
      description={d ? `${d.guest_name}${d.check_in_date ? ` · ${d.check_in_date} → ${d.check_out_date}` : ""}` : undefined}
      onClose={onClose}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Link to={`/trip/${encodeURIComponent(name)}`}>
            <Button variant="outline"><Printer className="size-4" />{t("Confirmation")}</Button>
          </Link>
          {canAdvance && !adv && d?.total != null && (
            <Button variant="outline" onClick={() => planAdvance()}>{t("Take trip advance")}</Button>
          )}
          {cancellable && !preview && (
            <Button variant="outline" onClick={askCancel}>{t("Cancel whole trip")}</Button>
          )}
        </div>
      }
    >
      {!d && !error && <p className="py-10 text-center text-zinc-400">{t("Loading…")}</p>}
      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{translate(error)}</div>
      )}
      {d && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge tone={STATUS_TONE[d.status] ?? "zinc"}>{statusLabel(d.status)}</Badge>
            {d.total != null && (
              <span className="text-sm text-zinc-600">
                {t("Total {amount} · advance paid {paid}", {
                  amount: `${sym}${inr(d.total)}`, paid: `${sym}${inr(d.advance_paid ?? 0)}` })}
                {(d.advance_due ?? 0) > 0 && (
                  <span className="text-amber-700">
                    {" · "}{t("advance due {amount}", { amount: `${sym}${inr(d.advance_due)}` })}
                  </span>
                )}
              </span>
            )}
          </div>
          <ol className="space-y-2">
            {d.legs.map((l, i) => (
              <li key={l.reservation} className="rounded-lg border border-zinc-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex size-5 items-center justify-center rounded-full bg-zinc-800 text-[11px] font-semibold text-white">{i + 1}</span>
                  <span className="font-semibold">{l.property_name}</span>
                  {l.city && <span className="text-xs text-zinc-400">{l.city}</span>}
                  <Badge className="ml-auto" tone={STATUS_TONE[l.status] ?? "zinc"}>{statusLabel(l.status)}</Badge>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-zinc-600">
                  <span>{l.check_in_date} → {l.check_out_date}</span>
                  <span>{l.room_type_name}{l.room ? ` · ${l.room}` : ""}</span>
                  <span>{l.currency_symbol}{inr(l.amount_after_tax)}</span>
                  {l.advance_paid > 0 && <span>{t("Paid {amount}", { amount: `${l.currency_symbol}${inr(l.advance_paid)}` })}</span>}
                  {l.deposit_due > 0 && <span className="text-amber-700">{t("Advance due {amount} ({pct}%)", { amount: `${l.currency_symbol}${inr(l.deposit_due)}`, pct: String(l.advance_percent) })}</span>}
                  {l.cancellation_number && <span>{l.cancellation_number}</span>}
                </div>
                <button className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
                  onClick={() => openLeg(l.property, l.reservation)}>
                  <ExternalLink className="size-3" />{t("Open {ref} to change dates, take an advance or cancel this stay", { ref: l.reservation })}
                </button>
              </li>
            ))}
          </ol>
          {adv && (
            <div className="space-y-2 rounded-lg border border-brand-200 bg-brand-50/40 p-3 text-sm">
              <p className="font-medium">{t("One advance for the whole trip")}</p>
              <div className="grid gap-2 sm:grid-cols-3">
                <input className={inputCls} type="number" min={0} aria-label={t("Amount")}
                  value={adv.amount} onChange={(e) => setAdv({ ...adv, amount: e.target.value })}
                  onBlur={() => adv.amount && planAdvance(adv.amount)} />
                <select className={inputCls} aria-label={t("Payment mode")} value={adv.mode}
                  onChange={(e) => setAdv({ ...adv, mode: e.target.value })}>
                  {loc.payment_modes.map((m) => <option key={m} value={m}>{t(m)}</option>)}
                </select>
                <Button variant="outline" onClick={() => planAdvance(adv.amount)}>{t("Show split")}</Button>
              </div>
              {adv.plan && (
                <>
                  <p className="text-xs text-zinc-500">
                    {t("Each stay first gets the advance its own dates ask for, earliest first. Anything more goes to the earliest stay, never past its bill.")}
                  </p>
                  {adv.plan.legs.map((l) => (
                    <div key={l.reservation} className="flex justify-between gap-2">
                      <span>{l.property_name} · {l.check_in_date} · {t("due {amount} ({pct}%)", {
                        amount: `${adv.plan!.currency_symbol}${inr(l.advance_due)}`, pct: String(l.advance_percent) })}</span>
                      <span className="font-medium">{adv.plan!.currency_symbol}{inr(l.share)}</span>
                    </div>
                  ))}
                </>
              )}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAdv(null)}>{t("Close")}</Button>
                <Button disabled={busy || !adv.plan || Number(adv.amount) !== adv.plan.amount} onClick={takeAdvance}>
                  {adv.plan ? t("Take {amount}", { amount: `${adv.plan.currency_symbol}${inr(adv.plan.amount)}` }) : t("Take advance")}
                </Button>
              </div>
            </div>
          )}
          {preview && (
            <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50/50 p-3 text-sm">
              <p className="font-medium">{t("Cancel every confirmed stay, each under its own property's policy:")}</p>
              {preview.legs.map((l) => (
                <div key={l.reservation} className="flex justify-between">
                  <span>{l.property} · {l.reservation}</span>
                  <span>{l.estimated_fee > 0 ? `${l.currency_symbol}${inr(l.estimated_fee)}` : t("No fee")}</span>
                </div>
              ))}
              {preview.not_cancellable.length > 0 && (
                <p className="text-xs text-zinc-500">
                  {t("Not cancelled (already started or finished): {refs}", {
                    refs: preview.not_cancellable.map((x) => x.reservation).join(", ") })}
                </p>
              )}
              <select className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}>
                {REASONS.map((r) => <option key={r} value={r}>{t(r)}</option>)}
              </select>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setPreview(null)}>{t("Keep trip")}</Button>
                <Button disabled={busy} onClick={cancelTrip}>
                  {preview.total_fee
                    ? t("Cancel trip, fees {amount}", { amount: `${preview.legs[0]?.currency_symbol ?? ""}${inr(preview.total_fee)}` })
                    : t("Cancel trip")}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </Sheet>
  )
}
