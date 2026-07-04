import { useEffect, useState } from "react"
import {
  ArrowLeft,
  Bot,
  CalendarPlus,
  LogIn,
  LogOut,
  Phone,
  Star,
  XCircle,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { call } from "../lib/api"
import { Badge } from "../components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { cn } from "../lib/utils"

interface Journey {
  guest: {
    name: string
    full_name: string
    phone: string | null
    email: string | null
    vip: 0 | 1
    nationality: string | null
    notes: string | null
  }
  stats: {
    bookings: number
    stays: number
    nights: number
    lifetime_value: number
    first_seen: string
  }
  timeline: {
    ts: string
    type: "booking" | "check_in" | "check_out" | "cancelled" | "agent"
    title: string
    detail: string
    amount?: number
    channel?: string
    reference?: string
  }[]
}

const inr = (n: number) =>
  Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })

const eventIcon = {
  booking: CalendarPlus,
  check_in: LogIn,
  check_out: LogOut,
  cancelled: XCircle,
  agent: Bot,
}

const eventTone = {
  booking: "bg-brand-50 text-brand-700 border-brand-100",
  check_in: "bg-emerald-50 text-emerald-700 border-emerald-100",
  check_out: "bg-zinc-100 text-zinc-600 border-zinc-200",
  cancelled: "bg-rose-50 text-rose-600 border-rose-100",
  agent: "bg-indigo-50 text-indigo-700 border-indigo-100",
}

function StatTile(props: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold">{props.value}</div>
        <div className="mt-0.5 text-xs font-medium uppercase tracking-wider text-zinc-500">
          {props.label}
        </div>
      </CardContent>
    </Card>
  )
}

export default function GuestJourney() {
  const { name } = useParams()
  const [data, setData] = useState<Journey | null>(null)

  useEffect(() => {
    if (name) call<Journey>("kamra.api.guest_journey", { guest: name }).then(setData)
  }, [name])

  if (!data) {
    return <p className="py-10 text-center text-sm text-zinc-400">Loading…</p>
  }

  const { guest, stats, timeline } = data

  return (
    <div>
      <Link
        to="/guests"
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All guests
      </Link>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="flex size-12 items-center justify-center rounded-full bg-brand-50 text-lg font-semibold text-brand-700">
          {guest.full_name?.slice(0, 1) ?? "G"}
        </div>
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            {guest.full_name}
            {Boolean(guest.vip) && (
              <Star
                className="size-4 fill-amber-400 text-amber-400"
                aria-label="VIP"
              />
            )}
          </h1>
          <p className="flex items-center gap-3 text-sm text-zinc-500">
            {guest.phone && (
              <span className="inline-flex items-center gap-1">
                <Phone className="size-3.5" aria-hidden />
                {guest.phone}
              </span>
            )}
            {guest.email && <span>{guest.email}</span>}
            {guest.nationality && <span>{guest.nationality}</span>}
          </p>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Bookings" value={String(stats.bookings)} />
        <StatTile label="Stays" value={String(stats.stays)} />
        <StatTile label="Nights" value={String(stats.nights)} />
        <StatTile
          label="Lifetime value"
          value={`₹${inr(stats.lifetime_value)}`}
        />
      </div>

      {guest.notes && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-medium">Notes: </span>
          {guest.notes}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Journey</CardTitle>
          <span className="text-xs text-zinc-400">
            {timeline.length} events · newest first
          </span>
        </CardHeader>
        <CardContent>
          {timeline.length === 0 ? (
            <p className="py-4 text-sm text-zinc-400">
              No activity yet — their story starts with the first booking.
            </p>
          ) : (
            <ol className="relative ml-3 space-y-5 border-l border-zinc-200 pb-1">
              {timeline.map((e, i) => {
                const Icon = eventIcon[e.type]
                return (
                  <li key={i} className="relative pl-8">
                    <span
                      className={cn(
                        "absolute -left-[13px] top-0 flex size-[26px] items-center justify-center rounded-full border",
                        eventTone[e.type],
                      )}
                    >
                      <Icon className="size-3.5" aria-hidden />
                    </span>
                    <div className="flex flex-wrap items-baseline gap-x-3">
                      <span className="text-sm font-medium">{e.title}</span>
                      {e.amount ? (
                        <span className="text-sm text-zinc-500">
                          ₹{inr(e.amount)}
                        </span>
                      ) : null}
                      {e.channel && <Badge tone="indigo">{e.channel}</Badge>}
                      <span className="ml-auto text-xs text-zinc-400">
                        {e.ts.slice(0, 16)}
                      </span>
                    </div>
                    {e.detail && (
                      <p className="mt-0.5 text-sm text-zinc-500">{e.detail}</p>
                    )}
                  </li>
                )
              })}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
