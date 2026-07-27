import { useState } from "react"
import { Search, BedDouble, MapPin, Loader2 } from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { Card, CardContent } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cur, moneyLocale } from "../lib/money"

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

function isoToday() {
  return new Date().toISOString().slice(0, 10)
}
function plusDays(iso: string, n: number) {
  const d = new Date(iso)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

export default function CRS() {
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

  const checkOut = plusDays(checkIn, Math.max(1, nights))

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
      setDone(`Booked ${r.reservation} at ${booking.property_name}.`)
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
        <h1 className="text-xl font-bold text-zinc-800">Central reservations</h1>
        <p className="text-xs text-zinc-500">
          Find a room across every property you manage, and book into
          whichever has space.
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-5">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Check-in</span>
            <input type="date" className={inputCls} value={checkIn}
              onChange={(e) => setCheckIn(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Nights</span>
            <input type="number" min={1} className={inputCls} value={nights}
              onChange={(e) => setNights(Math.max(1, Number(e.target.value)))} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Adults</span>
            <input type="number" min={1} className={inputCls} value={adults}
              onChange={(e) => setAdults(Math.max(1, Number(e.target.value)))} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Children</span>
            <input type="number" min={0} className={inputCls} value={children}
              onChange={(e) => setChildren(Math.max(0, Number(e.target.value)))} />
          </label>
          <div className="flex items-end">
            <Button className="w-full" disabled={busy} onClick={search}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      {done && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {done}
        </div>
      )}

      {data && (
        <div className="space-y-3">
          <p className="text-sm text-zinc-500">
            {data.properties.length} propert
            {data.properties.length === 1 ? "y" : "ies"} with space ·{" "}
            {data.nights} night{data.nights === 1 ? "" : "s"},{" "}
            {data.adults} adult{data.adults === 1 ? "" : "s"}
            {data.children ? `, ${data.children} children` : ""}
          </p>
          {data.properties.length === 0 && (
            <Card><CardContent className="p-8 text-center text-sm text-zinc-400">
              No rooms across the chain for these dates and party.
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
                    {p.available_rooms} rooms · from {cur()}{inr(p.from_rate)}/night
                  </span>
                </div>
                <div className="divide-y divide-zinc-100">
                  {p.room_types.map((rt) => (
                    <div key={rt.room_type} className="flex flex-wrap items-center gap-3 py-2.5">
                      <BedDouble className="size-4 shrink-0 text-zinc-400" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-zinc-800">{rt.room_type_name}</div>
                        <div className="text-xs text-zinc-500">
                          {rt.available} left · sleeps {rt.adults_capacity} · {cur()}{inr(rt.per_night)}/night
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold">{cur()}{inr(rt.total)}</div>
                        <div className="text-[11px] text-zinc-400">total, taxes in</div>
                      </div>
                      <Button variant="outline"
                        onClick={() => { setBooking({ property: p.property, property_name: p.property_name, rt }); setGuest({ name: "", phone: "" }) }}>
                        Book
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {booking && (
        <Sheet
          title={`Book ${booking.rt.room_type_name}`}
          description={`${booking.property_name} · ${checkIn} → ${checkOut} · ${cur()}${inr(booking.rt.total)} total`}
          onClose={() => setBooking(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setBooking(null)}>Cancel</Button>
              <Button disabled={busy || !guest.name.trim()} onClick={() => book().then(() => setBooking(null))}>
                Confirm booking
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-zinc-600">Guest name</span>
              <input className={inputCls} value={guest.name} autoFocus
                onChange={(e) => setGuest({ ...guest, name: e.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-zinc-600">Phone</span>
              <input className={inputCls} value={guest.phone} placeholder="+91 …"
                onChange={(e) => setGuest({ ...guest, phone: e.target.value })} />
            </label>
          </div>
        </Sheet>
      )}
    </div>
  )
}
