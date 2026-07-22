import { useCallback, useEffect, useState } from "react"
import {
  ArrowLeft,
  Bot,
  CalendarPlus,
  Fingerprint,
  LogIn,
  LogOut,
  Mail,
  MapPin,
  Merge,
  Phone,
  ShieldOff,
  Star,
  XCircle,
} from "lucide-react"
import { Link, useNavigate, useOutletContext, useParams } from "react-router-dom"
import { call, guestSearch, type GuestHit } from "../lib/api"
import { serverError, updateResource } from "../lib/resource"
import type { ShellContext } from "../AppShell"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card"
import { cn } from "../lib/utils"
import { toFullPath } from "../lib/routing"

/** Guest profile hub - the person is the center, stays hang off them.
 * Everything the desk needs when a returning guest calls: history at a
 * glance (the stay strip), what's coming up, and the profile actions
 * (book, merge duplicates, anonymize). */

interface ResRow {
  name: string
  status: string
  source: string
  channel: string | null
  room: string | null
  room_type: string | null
  check_in_date: string
  check_out_date: string
  nights: number
  amount_after_tax: number
  company: string | null
}

interface Journey {
  guest: {
    name: string
    full_name: string
    phone: string | null
    email: string | null
    vip: 0 | 1
    nationality: string | null
    id_type: string | null
    id_number: string | null
    blacklisted: 0 | 1
    blacklist_reason: string | null
    address: string
    notes: string | null
  }
  stats: {
    bookings: number
    stays: number
    nights: number
    lifetime_value: number
    first_seen: string
  }
  reservations: ResRow[]
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

const stripTone: Record<string, string> = {
  "Checked Out": "bg-brand-600",
  "Checked In": "bg-emerald-500",
  Confirmed: "bg-sky-400",
  Cancelled: "bg-rose-300",
  "No Show": "bg-rose-300",
}

/** Every stay as one block, width ∝ nights - a guest's whole relationship
 * with the hotel readable in half a second. */
function StayStrip({ rows }: { rows: ResRow[] }) {
  const ordered = [...rows].sort((a, b) =>
    a.check_in_date.localeCompare(b.check_in_date),
  )
  if (ordered.length === 0) return null
  return (
    <div>
      <div className="flex h-2.5 items-stretch gap-[3px]" aria-hidden>
        {ordered.map((r) => (
          <span
            key={r.name}
            title={`${r.check_in_date} → ${r.check_out_date} · ${r.status} · ₹${inr(r.amount_after_tax)}`}
            className={cn(
              "rounded-sm",
              stripTone[r.status] ?? "bg-zinc-300",
            )}
            style={{ flexGrow: Math.max(1, r.nights || 1), flexBasis: 8 }}
          />
        ))}
      </div>
      <div className="mt-1.5 flex gap-3 text-[10px] text-zinc-400">
        <span>
          <span className="mr-1 inline-block size-2 rounded-sm bg-brand-600 align-middle" />
          stayed
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-sm bg-emerald-500 align-middle" />
          in-house
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-sm bg-sky-400 align-middle" />
          upcoming
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-sm bg-rose-300 align-middle" />
          cancelled
        </span>
      </div>
    </div>
  )
}

function MergePanel(props: {
  survivor: string
  survivorName: string
  onDone: () => void
}) {
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<GuestHit[]>([])
  const [picked, setPicked] = useState<GuestHit | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (picked || q.trim().length < 2) {
      setHits([])
      return
    }
    const t = setTimeout(
      () =>
        guestSearch(q)
          .then((r) => setHits(r.filter((h) => h.name !== props.survivor)))
          .catch(() => setHits([])),
      250,
    )
    return () => clearTimeout(t)
  }, [q, picked, props.survivor])

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
      <p className="text-sm font-medium">Merge a duplicate into this profile</p>
      <p className="mb-2 mt-0.5 text-xs text-zinc-500">
        The duplicate's stays, bills and tickets move to{" "}
        <span className="font-medium">{props.survivorName}</span>, then the
        duplicate is deleted. This can't be undone.
      </p>
      <div className="relative max-w-sm">
        <input
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
          placeholder="Find the duplicate by name or phone"
          value={picked ? picked.full_name : q}
          onChange={(e) => {
            setPicked(null)
            setQ(e.target.value)
          }}
        />
        {hits.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-lg">
            {hits.map((h) => (
              <li key={h.name}>
                <button
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50"
                  onClick={() => setPicked(h)}
                >
                  <span className="font-medium">{h.full_name}</span>
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
      <div className="mt-3 flex items-center gap-2">
        <Button
          disabled={!picked || busy}
          onClick={async () => {
            if (!picked) return
            setBusy(true)
            setError(null)
            try {
              await call("kamra.api.merge_guests", {
                source: picked.name,
                target: props.survivor,
              })
              props.onDone()
            } catch (e) {
              setError(serverError(e))
            } finally {
              setBusy(false)
            }
          }}
        >
          {busy
            ? "Merging…"
            : picked
              ? `Merge ${picked.full_name} into this profile`
              : "Merge"}
        </Button>
        {error && <span className="text-xs text-rose-600">{error}</span>}
      </div>
    </div>
  )
}

function StatCell(props: { label: string; value: string }) {
  return (
    <div>
      <div className="text-lg font-semibold leading-tight">{props.value}</div>
      <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-400">
        {props.label}
      </div>
    </div>
  )
}

export default function GuestJourney() {
  const { name } = useParams()
  const navigate = useNavigate()
  const { openBooking } = useOutletContext<ShellContext>()
  const [data, setData] = useState<Journey | null>(null)
  const [merging, setMerging] = useState(false)
  const [confirmAnon, setConfirmAnon] = useState(false)
  const [notes, setNotes] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (name)
      call<Journey>("kamra.api.guest_journey", { guest: name }).then((d) => {
        setData(d)
        setNotes(d.guest.notes ?? "")
      })
  }, [name])

  useEffect(load, [load])

  if (!data || notes === null) {
    return <p className="py-10 text-center text-sm text-zinc-400">Loading…</p>
  }

  const { guest, stats, timeline, reservations } = data
  const today = new Date().toISOString().slice(0, 10)
  const upcoming = reservations
    .filter((r) => r.status === "Confirmed" && r.check_in_date >= today)
    .sort((a, b) => a.check_in_date.localeCompare(b.check_in_date))
  const avgNight = stats.nights ? stats.lifetime_value / stats.nights : 0

  async function saveField(patch: Record<string, unknown>) {
    setBusy(true)
    try {
      await updateResource("Guest", guest.name, patch)
      load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <Link
        to="/guests"
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All guests
      </Link>

      {/* identity card */}
      <Card className="mb-4">
        <CardContent className="py-5">
          <div className="flex flex-wrap items-start gap-4">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 text-xl font-semibold text-brand-700">
              {guest.full_name?.slice(0, 1) ?? "G"}
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
                {guest.full_name}
                {Boolean(guest.vip) && (
                  <Star
                    className="size-4 fill-amber-400 text-amber-400"
                    aria-label="VIP"
                  />
                )}
                {Boolean(guest.blacklisted) && (
                  <Badge tone="rose">Blacklisted</Badge>
                )}
              </h1>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-500">
                {guest.phone && (
                  <span className="inline-flex items-center gap-1">
                    <Phone className="size-3.5" aria-hidden />
                    {guest.phone}
                  </span>
                )}
                {guest.email && (
                  <span className="inline-flex items-center gap-1">
                    <Mail className="size-3.5" aria-hidden />
                    {guest.email}
                  </span>
                )}
                {guest.address && (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="size-3.5" aria-hidden />
                    {guest.address}
                  </span>
                )}
                {guest.id_type && (
                  <span className="inline-flex items-center gap-1">
                    <Fingerprint className="size-3.5" aria-hidden />
                    {guest.id_type} {guest.id_number ?? ""}
                  </span>
                )}
              </p>
              <div className="mt-4">
                <StayStrip rows={reservations} />
              </div>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="flex gap-2">
                <Button
                  onClick={() =>
                    openBooking({
                      guest: guest.name,
                      guest_name: guest.full_name,
                      phone: guest.phone ?? undefined,
                      stays: stats.stays,
                    })
                  }
                >
                  <CalendarPlus className="size-4" aria-hidden />
                  Book a stay
                </Button>
              </div>
              <div className="flex gap-6 text-right">
                <StatCell label="Stays" value={String(stats.stays)} />
                <StatCell label="Nights" value={String(stats.nights)} />
                <StatCell
                  label="Lifetime"
                  value={`₹${inr(stats.lifetime_value)}`}
                />
                <StatCell label="Per night" value={`₹${inr(avgNight)}`} />
              </div>
            </div>
          </div>
          {Boolean(guest.blacklisted) && guest.blacklist_reason && (
            <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {guest.blacklist_reason}
            </p>
          )}
        </CardContent>
      </Card>

      {upcoming.length > 0 && (
        <Card className="mb-4 border-sky-200">
          <CardContent className="py-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-sky-800">
              Upcoming
            </h2>
            <ul className="divide-y divide-zinc-100">
              {upcoming.map((r) => (
                <li
                  key={r.name}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm"
                >
                  <span className="font-medium">
                    {r.check_in_date} → {r.check_out_date}
                  </span>
                  <span className="text-zinc-500">
                    {r.room_type?.split("-").pop()}
                    {r.room ? ` · Room ${r.room.split("-").pop()}` : ""} ·{" "}
                    {r.nights} night{r.nights === 1 ? "" : "s"}
                  </span>
                  {r.company && <Badge tone="zinc">{r.company}</Badge>}
                  <span className="ml-auto flex items-center gap-3">
                    <span>₹{inr(r.amount_after_tax)}</span>
                    <a
                      href={toFullPath(`/grc/${encodeURIComponent(r.name)}`)}
                      className="font-medium text-brand-700 hover:underline"
                    >
                      GRC
                    </a>
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Journey</CardTitle>
            <span className="text-xs text-zinc-400">
              {timeline.length} events · newest first
            </span>
          </CardHeader>
          <CardContent>
            {timeline.length === 0 ? (
              <p className="py-4 text-sm text-zinc-400">
                No activity yet - their story starts with the first booking.
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
                        {e.reference && e.type !== "agent" ? (
                          <Link
                            to={`/reservations?q=${encodeURIComponent(e.reference)}`}
                            className="text-sm font-medium text-brand-700 hover:underline"
                            title={`Open ${e.reference}`}
                          >
                            {e.title}
                          </Link>
                        ) : (
                          <span className="text-sm font-medium">{e.title}</span>
                        )}
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
                        <p className="mt-0.5 text-sm text-zinc-500">
                          {e.detail}
                        </p>
                      )}
                    </li>
                  )
                })}
              </ol>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notes & preferences</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                className="min-h-24 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
                placeholder="Allergies, room preferences, how they take their chai…"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <div className="mt-2 flex items-center gap-3">
                <Button
                  variant="outline"
                  disabled={busy || notes === (guest.notes ?? "")}
                  onClick={() => saveField({ guest_notes: notes })}
                >
                  Save notes
                </Button>
                <label className="flex items-center gap-1.5 text-sm text-zinc-600">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={Boolean(guest.vip)}
                    disabled={busy}
                    onChange={(e) =>
                      saveField({ vip: e.target.checked ? 1 : 0 })
                    }
                  />
                  VIP
                </label>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Profile actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {merging ? (
                <MergePanel
                  survivor={guest.name}
                  survivorName={guest.full_name}
                  onDone={() => {
                    setMerging(false)
                    load()
                  }}
                />
              ) : (
                <Button variant="outline" onClick={() => setMerging(true)}>
                  <Merge className="size-4" aria-hidden />
                  Merge a duplicate
                </Button>
              )}
              <div>
                <Button
                  variant="outline"
                  className={cn(
                    confirmAnon && "border-rose-300 text-rose-600",
                  )}
                  disabled={busy}
                  onClick={async () => {
                    if (!confirmAnon) {
                      setConfirmAnon(true)
                      return
                    }
                    setBusy(true)
                    try {
                      await call("kamra.api.anonymize_guest", {
                        guest: guest.name,
                      })
                      navigate("/guests")
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  <ShieldOff className="size-4" aria-hidden />
                  {confirmAnon
                    ? "Confirm - erase identity forever"
                    : "Anonymize profile"}
                </Button>
                <p className="mt-1.5 text-xs text-zinc-400">
                  Erases name, contact and ID everywhere; stays and bills stay
                  on the books. For data-erasure requests.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
