import { useEffect, useState } from "react"
import { ArrowLeft, Printer } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { Button } from "../components/ui/button"

/** Printable Guest Registration Card (GRC) — sign at check-in. */

interface Grc {
  property: {
    property_name: string
    logo_url: string | null
    address: string
    gstin: string | null
    phone: string | null
    checkin_time: string
    checkout_time: string
  }
  reservation: {
    name: string
    room: string
    room_type: string
    check_in_date: string
    check_out_date: string
    nights: number
    adults: number
    children: number
    rate_total: number
    advance_paid: number
    company: string | null
    booked_by_name: string | null
    source: string
    special_requests: string | null
  }
  guest: {
    full_name: string
    phone: string | null
    email: string | null
    nationality: string | null
    id_type: string | null
    id_number: string | null
    address: string
  }
}

const inr = (n: number) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: 0 })

function Row(props: { label: string; value?: string | null }) {
  return (
    <div className="flex border-b border-zinc-200 py-1.5 text-sm">
      <span className="w-40 shrink-0 text-zinc-500">{props.label}</span>
      <span className="font-medium">{props.value || "—"}</span>
    </div>
  )
}

export default function RegistrationCard() {
  const { name } = useParams()
  const [d, setD] = useState<Grc | null>(null)

  useEffect(() => {
    if (name)
      call<Grc>("kamra.api.registration_card", { reservation: name }).then(setD)
  }, [name])

  if (!d) return <p className="py-10 text-center text-zinc-400">Loading…</p>

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft className="size-4" aria-hidden /> Today
        </Link>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden /> Print GRC
        </Button>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-6 print:border-0">
        <div className="mb-5 flex items-start justify-between border-b border-zinc-300 pb-4">
          <div>
            <h1 className="text-lg font-bold">{d.property.property_name}</h1>
            <p className="text-xs text-zinc-500">{d.property.address}</p>
            <p className="text-xs text-zinc-500">
              {d.property.gstin && <>GSTIN {d.property.gstin} · </>}
              {d.property.phone}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold">GUEST REGISTRATION CARD</p>
            <p className="text-xs text-zinc-500">{d.reservation.name}</p>
          </div>
        </div>

        <div className="grid gap-x-8 sm:grid-cols-2">
          <div>
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">Guest</h2>
            <Row label="Name" value={d.guest.full_name} />
            <Row label="Phone" value={d.guest.phone} />
            <Row label="Email" value={d.guest.email} />
            <Row label="Nationality" value={d.guest.nationality} />
            <Row label="ID" value={d.guest.id_type ? `${d.guest.id_type} · ${d.guest.id_number ?? ""}` : null} />
            <Row label="Address" value={d.guest.address} />
            {d.reservation.company && <Row label="Company" value={d.reservation.company} />}
            {d.reservation.booked_by_name && (
              <Row label="Booked by" value={d.reservation.booked_by_name} />
            )}
          </div>
          <div>
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">Stay</h2>
            <Row label="Room" value={`${d.reservation.room} · ${d.reservation.room_type}`} />
            <Row label="Check-in" value={`${d.reservation.check_in_date} (${d.property.checkin_time.slice(0, 5)})`} />
            <Row label="Check-out" value={`${d.reservation.check_out_date} (${d.property.checkout_time.slice(0, 5)})`} />
            <Row label="Nights" value={String(d.reservation.nights)} />
            <Row label="Guests" value={`${d.reservation.adults} adult(s)${d.reservation.children ? ` + ${d.reservation.children} child` : ""}`} />
            <Row label="Stay total" value={`₹${inr(d.reservation.rate_total)} (incl. GST)`} />
            <Row label="Advance paid" value={`₹${inr(d.reservation.advance_paid)}`} />
            <Row label="Source" value={d.reservation.source} />
          </div>
        </div>

        {d.reservation.special_requests && (
          <p className="mt-3 text-sm"><span className="text-zinc-500">Requests: </span>{d.reservation.special_requests}</p>
        )}

        <p className="mt-6 text-[11px] leading-relaxed text-zinc-500">
          I certify the above details are correct. I agree to the hotel's
          policies on check-out time, damage to property and applicable
          taxes, and consent to my details being kept in the guest register
          as required by law.
        </p>

        <div className="mt-10 grid grid-cols-2 gap-8">
          <div className="border-t border-zinc-400 pt-1 text-center text-xs text-zinc-500">
            Guest signature
          </div>
          <div className="border-t border-zinc-400 pt-1 text-center text-xs text-zinc-500">
            Front desk (name & sign)
          </div>
        </div>
      </div>
    </div>
  )
}
