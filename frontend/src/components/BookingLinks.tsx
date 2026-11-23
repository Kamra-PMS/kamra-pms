/*  Booking links with attribution (#560): build a /book link that opens a
    room type, dates and plan, tagged with a source (src) that the booking
    keeps (Reservation.source_tag), and see what each tag brought in
    (kamra.reports.booking_link_sources). */

import { useEffect, useMemo, useState } from "react"
import { callGuest, call } from "../lib/api"
import { serverError } from "../lib/resource"
import { fmtMoney } from "../lib/money"
import { t as translate, useUILanguage } from "../lib/i18n"
import { Button } from "./ui/button"

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

type Showcase = {
  room_types: { name: string; room_type_name: string }[]
  meal_plans: { name: string; label: string }[]
}
type Sources = {
  enabled: boolean
  rows: { tag: string; bookings: number; room_nights: number; amount: number }[]
}

export default function BookingLinks({ property, slug }: { property: string; slug?: string | null }) {
  useUILanguage()
  const [show, setShow] = useState<Showcase | null>(null)
  const [sources, setSources] = useState<Sources | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [room, setRoom] = useState("")
  const [plan, setPlan] = useState("")
  const [checkIn, setCheckIn] = useState("")
  const [checkOut, setCheckOut] = useState("")
  const [tag, setTag] = useState("")
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    callGuest<Showcase>("kamra.public_api.showcase", { property }).then(setShow).catch(() => setShow(null))
    call<Sources>("kamra.reports.booking_link_sources", { property })
      .then(setSources)
      .catch((e) => setErr(serverError(e)))
  }, [property])

  const link = useMemo(() => {
    const qs = new URLSearchParams()
    if (slug) qs.set("property", slug)
    if (room) qs.set("room", room)
    if (plan) qs.set("plan", plan)
    const src = tag.trim().replace(/[^A-Za-z0-9_.-]+/g, "-").slice(0, 60)
    if (src) qs.set("src", src)
    const dates = checkIn && checkOut && checkOut > checkIn ? `/${checkIn}/${checkOut}/2/0` : ""
    const q = qs.toString()
    return `${window.location.origin}/book${dates}${q ? `?${q}` : ""}`
  }, [slug, room, plan, checkIn, checkOut, tag])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="space-y-5">
      {sources && !sources.enabled ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {translate("Booking links are switched off: the page opens, but bookings don't keep the tag. Turn them on in Settings, Booking Engine.")}
        </p>
      ) : null}
      {err ? <p className="text-sm text-rose-600">{translate(err)}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">{translate("Room type")}</span>
          <select className={inputCls} value={room} onChange={(e) => setRoom(e.target.value)}>
            <option value="">{translate("Any room type")}</option>
            {(show?.room_types ?? []).map((r) => <option key={r.name} value={r.name}>{r.room_type_name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">{translate("Plan")}</span>
          <select className={inputCls} value={plan} onChange={(e) => setPlan(e.target.value)} disabled={!room}>
            <option value="">{translate("Room only or the guest's pick")}</option>
            {(show?.meal_plans ?? []).map((m) => <option key={m.name} value={m.name}>{m.label}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">{translate("Check-in (optional)")}</span>
          <input type="date" className={inputCls} value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-zinc-600">{translate("Check-out (optional)")}</span>
          <input type="date" className={inputCls} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-sm font-medium text-zinc-600">{translate("Source tag")}</span>
          <input className={inputCls} maxLength={60} placeholder={translate("e.g. instagram-bio, newsletter-nov")}
            value={tag} onChange={(e) => setTag(e.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded-lg bg-zinc-100 px-3 py-2 text-xs">{link}</code>
        <Button variant="outline" onClick={() => void copy()}>{copied ? translate("Copied") : translate("Copy link")}</Button>
      </div>

      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-400">
          {translate("Bookings by source tag, last 90 days")}
        </p>
        {sources?.rows.length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-zinc-400">
              <tr>
                <th className="py-1.5 pr-3">{translate("Tag")}</th>
                <th className="py-1.5 pr-3 text-right">{translate("Bookings")}</th>
                <th className="py-1.5 pr-3 text-right">{translate("Room nights")}</th>
                <th className="py-1.5 text-right">{translate("Booked value")}</th>
              </tr>
            </thead>
            <tbody>
              {sources.rows.map((r) => (
                <tr key={r.tag} className="border-t border-zinc-100">
                  <td className="py-1.5 pr-3 font-mono text-xs">{r.tag}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{r.bookings}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{r.room_nights}</td>
                  <td className="py-1.5 text-right tabular-nums">{fmtMoney(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-zinc-400">{translate("No bookings from tagged links yet.")}</p>
        )}
      </div>
    </div>
  )
}
