import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Building2,
  PartyPopper,
  Receipt,
  UserCircle2,
  Users,
} from "lucide-react"

import { call } from "../lib/api"

/** The connective tissue, rendered: one strip of chips on any record that
 *  jumps straight to its guest, folios (billing), company, group or event.
 *  Same component everywhere - reservations, events, groups, folios. */

interface Links {
  guest: string | null
  guest_name: string | null
  reservations: { name: string; status: string; check_in_date: string }[]
  folios: {
    name: string
    folio_type: string
    status: string
    balance: number
    invoice_number: string | null
  }[]
  company: string | null
  group_booking: string | null
  group_name: string | null
  event: string | null
  event_type: string | null
}

const chipCls =
  "inline-flex items-center gap-1.5 rounded-full border border-zinc-200 " +
  "bg-white px-2.5 py-1 text-xs font-medium text-zinc-600 " +
  "hover:border-brand-400 hover:text-brand-700 transition"

export default function LinkedRecords({
  doctype,
  name,
  exclude = [],
}: {
  doctype: string
  name: string
  /** hide chip kinds that would link back to the current screen */
  exclude?: ("guest" | "folio" | "company" | "group" | "event")[]
}) {
  const [links, setLinks] = useState<Links | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    call<Links>("kamra.api.linked_records", { doctype, name })
      .then(setLinks)
      .catch(() => setLinks(null))
  }, [doctype, name])

  if (!links) return null
  const inr = (n: number) =>
    Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })

  const chips: React.ReactNode[] = []
  if (links.guest && !exclude.includes("guest"))
    chips.push(
      <button
        key="guest"
        className={chipCls}
        onClick={() => navigate(`/guests/${encodeURIComponent(links.guest!)}`)}
      >
        <UserCircle2 className="size-3.5" aria-hidden />
        {links.guest_name || "Guest"}
      </button>,
    )
  if (!exclude.includes("folio"))
    for (const f of links.folios)
      chips.push(
        <button
          key={f.name}
          className={chipCls}
          onClick={() => navigate(`/billing/${encodeURIComponent(f.name)}`)}
          title={f.invoice_number ? `Invoice ${f.invoice_number}` : "Open folio"}
        >
          <Receipt className="size-3.5" aria-hidden />
          {f.folio_type} folio
          <span
            className={
              f.balance > 0 ? "text-amber-600" : "text-zinc-400"
            }
          >
            ₹{inr(f.balance)}
          </span>
        </button>,
      )
  if (links.group_booking && !exclude.includes("group"))
    chips.push(
      <button
        key="group"
        className={chipCls}
        onClick={() => navigate("/groups")}
        title="Open Groups & Blocks"
      >
        <Users className="size-3.5" aria-hidden />
        {links.group_name || "Group"}
      </button>,
    )
  if (links.event && !exclude.includes("event"))
    chips.push(
      <button
        key="event"
        className={chipCls}
        onClick={() => navigate("/events")}
        title="Open Event Bookings"
      >
        <PartyPopper className="size-3.5" aria-hidden />
        {links.event_type || "Event"}
      </button>,
    )
  if (links.company && !exclude.includes("company"))
    chips.push(
      <button
        key="company"
        className={chipCls}
        onClick={() => navigate("/companies")}
        title="Open Companies"
      >
        <Building2 className="size-3.5" aria-hidden />
        {links.company}
      </button>,
    )

  if (chips.length === 0) return null
  return <div className="flex flex-wrap items-center gap-1.5">{chips}</div>
}
