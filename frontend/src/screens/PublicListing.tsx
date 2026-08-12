import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import {
  ArrowLeft,
  MapPin,
} from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { accentVars } from "../lib/accents"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cur, moneyLocale, adoptUiLocale } from "../lib/money"

const inr = (n: number) =>
  n.toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })

interface Resolved {
  kind: "listing" | "site"
  property: string
  listing_slug?: string
  location_slug?: string
  location_name?: string
  room_type?: string
  room_type_name?: string
}

interface Showcase {
  property: {
    name: string
    property_name: string
    description: string | null
    logo_url: string | null
    hero_image: string | null
    brand_accent: string | null
    payment_mode: string
    cleaning_fee: number
    security_deposit_amount: number
    minimum_nights: number
    booking_mode: string
    property_kind: string
    checkin_time: string
    checkout_time: string
    house_rules: string | null
    pets_policy: string | null
    children_policy: string | null
    city: string
    phone: string | null
  }
  room_types: {
    name: string
    room_type_name: string
    listing_slug: string | null
    description: string | null
    base_price: number
    adults_capacity: number
    bed_type: string | null
    room_view: string | null
    amenities: string[]
    media: { media_type: string; url: string; caption: string | null }[]
    location_name: string | null
    location_address: string | null
    google_maps_url: string | null
    latitude: number | null
    longitude: number | null
  }[]
  meal_plans: { name: string; code: string; label: string; price_per_adult: number }[]
}

interface StayResult {
  room_type: string
  rooms_left: number
  quote: {
    nights: number
    amount_after_tax: number
    cleaning_fee?: number
    totals?: { deposit_required?: number }
  } | null
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function todayPlus(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function nightsBetween(a: string, b: string) {
  const ms = new Date(b).getTime() - new Date(a).getTime()
  return Math.max(1, Math.round(ms / 86_400_000))
}

export default function PublicListing() {
  const { slug, checkin, checkout, adults: adultsParam, children: childrenParam } =
    useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [resolved, setResolved] = useState<Resolved | null>(null)
  const [data, setData] = useState<Showcase | null>(null)
  const [search, setSearch] = useState(() => ({
    check_in_date: checkin ?? todayPlus(1),
    nights:
      checkin && checkout ? nightsBetween(checkin, checkout) : 2,
    adults: Number(adultsParam ?? 2) || 2,
    children: Number(childrenParam ?? 0) || 0,
  }))
  const [results, setResults] = useState<Record<string, StayResult>>({})
  const [booking, setBooking] = useState<string | null>(null)
  const [form, setForm] = useState({
    guest_name: "",
    phone: "",
    email: "",
    meal_plan: "",
    special_requests: "",
  })
  const [done, setDone] = useState<{ reservation: string; amount: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const checkOut = useMemo(() => {
    const d = new Date(search.check_in_date)
    d.setDate(d.getDate() + Math.max(1, search.nights))
    return d.toISOString().slice(0, 10)
  }, [search])

  const listingSlug = resolved?.listing_slug
  const locationSlug = resolved?.location_slug
  const isStr = data?.property.property_kind === "Short Term Rental"
  const minNights = data?.property.minimum_nights || 1
  const primary = data?.room_types[0]
  const isSite = resolved?.kind === "site"

  useEffect(() => {
    if (!slug) return
    call<Resolved>("kamra.public_api.resolve_slug", { slug })
      .then((r) => {
        setResolved(r)
        const args: Record<string, string> = { property: r.property }
        if (r.listing_slug) args.listing_slug = r.listing_slug
        if (r.location_slug) args.location_slug = r.location_slug
        return call<Showcase>("kamra.public_api.showcase", args).then((d) => ({
          d,
          r,
        }))
      })
      .then(({ d, r }) => {
        adoptUiLocale(
          (d as unknown as { ui_locale?: { currency_symbol?: string; locale?: string } })
            .ui_locale,
        )
        setData(d)
        setForm((f) => ({ ...f, meal_plan: d.meal_plans[0]?.name ?? "" }))
        if (r.kind === "listing" && r.room_type) {
          setBooking(r.room_type)
        }
      })
      .catch((e) => setError(serverError(e)))
  }, [slug])

  useEffect(() => {
    if (!resolved) return
    navigate(
      `/stay/${slug}/${search.check_in_date}/${checkOut}/${search.adults}/${search.children}${searchParams.toString() ? `?${searchParams}` : ""}`,
      { replace: true },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, checkOut, slug])

  useEffect(() => {
    if (!resolved) return
    const t = setTimeout(() => {
      call<StayResult[]>("kamra.public_api.search_stay", {
        property: resolved.property,
        check_in_date: search.check_in_date,
        check_out_date: checkOut,
        adults: search.adults,
        children: search.children,
        listing_slug: listingSlug,
        location_slug: locationSlug,
      }).then((rows) => {
        const map: Record<string, StayResult> = {}
        rows.forEach((r) => (map[r.room_type] = r))
        setResults(map)
      })
    }, 300)
    return () => clearTimeout(t)
  }, [resolved, search, checkOut, listingSlug, locationSlug])

  async function submitBooking() {
    if (!booking || !resolved) return
    setBusy(true)
    setError(null)
    try {
      const res = await call<{ reservation: string; amount_after_tax: number }>(
        "kamra.public_api.book",
        {
          property: resolved.property,
          room_type: booking,
          check_in_date: search.check_in_date,
          check_out_date: checkOut,
          adults: search.adults,
          children: search.children,
          ...form,
        },
      )
      setDone({ reservation: res.reservation, amount: res.amount_after_tax })
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data || !resolved)
    return (
      <p className="py-20 text-center text-zinc-400">{error ?? "Loading…"}</p>
    )

  const p = data.property
  const accent = accentVars(p.brand_accent)
  const title =
    isSite
      ? resolved.location_name ?? p.property_name
      : primary?.room_type_name ?? p.property_name
  const hero =
    primary?.media[0]?.url ?? p.hero_image ?? undefined
  const quote = primary ? results[primary.name]?.quote : null
  const roomsLeft = primary ? results[primary.name]?.rooms_left ?? 0 : 0
  const confirmLabel =
    p.booking_mode === "Request to Book"
      ? "Request to book"
      : p.payment_mode === "Full online"
        ? "Confirm & pay"
        : "Confirm booking"

  return (
    <div className="min-h-[100dvh] bg-zinc-50" style={accent}>
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-5 py-3">
          <Link
            to="/book"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-900"
          >
            <ArrowLeft className="size-4" aria-hidden />
            All listings
          </Link>
          {p.logo_url && (
            <img src={p.logo_url} alt="" className="ml-auto h-8 w-auto" />
          )}
        </div>
      </header>

      <div className="relative mx-auto max-w-5xl px-5 pb-16 pt-6">
        {hero && (
          <div className="mb-6 overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-sm">
            <img
              src={hero}
              alt=""
              className="aspect-[21/9] w-full object-cover"
            />
            {primary && primary.media.length > 1 && (
              <div className="flex gap-2 overflow-x-auto border-t border-zinc-200 bg-white p-2">
                {primary.media.slice(1, 6).map((m, i) => (
                  <img
                    key={i}
                    src={m.url}
                    alt={m.caption ?? ""}
                    className="h-16 w-24 shrink-0 rounded-lg object-cover"
                  />
                ))}
              </div>
            )}
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-5">
          <div className="space-y-5 lg:col-span-3">
            <div>
              <p className="text-sm font-medium text-brand-700">{p.property_name}</p>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
                {title}
              </h1>
              {primary?.location_name && (
                <p className="mt-1 inline-flex items-center gap-1 text-sm text-zinc-500">
                  <MapPin className="size-4" aria-hidden />
                  {primary.location_address ?? primary.location_name}
                </p>
              )}
            </div>

            {primary?.description && (
              <p className="text-[15px] leading-relaxed text-zinc-600">
                {primary.description}
              </p>
            )}

            {primary && (
              <ul className="flex flex-wrap gap-2">
                {primary.amenities.map((a) => (
                  <Badge key={a} tone="zinc">
                    {a}
                  </Badge>
                ))}
              </ul>
            )}

            {isSite && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-800">
                  {isStr ? "Listings at this site" : "Rooms at this site"}
                </h2>
                {data.room_types.map((rt) => {
                  const r = results[rt.name]
                  return (
                    <div
                      key={rt.name}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4"
                    >
                      <div>
                        <p className="font-semibold text-zinc-900">{rt.room_type_name}</p>
                        <p className="text-sm text-zinc-500">
                          up to {rt.adults_capacity} guests · from {cur()}
                          {inr(rt.base_price)}/night
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {rt.listing_slug && (
                          <Button
                            variant="outline"
                            onClick={() => navigate(`/stay/${rt.listing_slug}`)}
                          >
                            View
                          </Button>
                        )}
                        <Button
                          disabled={!r?.quote}
                          onClick={() => setBooking(rt.name)}
                        >
                          Book
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {(p.house_rules || p.pets_policy) && (
              <div className="rounded-xl border border-zinc-200 bg-white p-5 text-sm">
                <h2 className="mb-2 font-semibold text-zinc-800">
                  {isStr ? "House rules" : "Policies"}
                </h2>
                {p.house_rules && (
                  <p className="whitespace-pre-line text-zinc-600">{p.house_rules}</p>
                )}
                {p.pets_policy && (
                  <p className="mt-2 text-zinc-600">Pets: {p.pets_policy}</p>
                )}
              </div>
            )}
          </div>

          <aside className="lg:col-span-2">
            <div className="sticky top-6 space-y-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-zinc-900">Your stay</h2>
              <div className="grid grid-cols-2 gap-3">
                <label className="col-span-2 block">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">
                    Check-in
                  </span>
                  <input
                    type="date"
                    className={inputCls}
                    value={search.check_in_date}
                    onChange={(e) =>
                      setSearch({ ...search, check_in_date: e.target.value })
                    }
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">
                    Nights
                  </span>
                  <input
                    type="number"
                    min={minNights}
                    className={inputCls}
                    value={search.nights}
                    onChange={(e) =>
                      setSearch({
                        ...search,
                        nights: Math.max(minNights, Number(e.target.value)),
                      })
                    }
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">
                    Guests
                  </span>
                  <input
                    type="number"
                    min={1}
                    className={inputCls}
                    value={search.adults}
                    onChange={(e) =>
                      setSearch({
                        ...search,
                        adults: Math.max(1, Number(e.target.value)),
                      })
                    }
                  />
                </label>
              </div>

              {quote ? (
                <div className="border-t border-zinc-100 pt-4">
                  <p className="text-3xl font-semibold tabular-nums text-zinc-900">
                    {cur()}
                    {inr(quote.amount_after_tax)}
                  </p>
                  <p className="text-sm text-zinc-500">
                    {quote.nights} night{quote.nights === 1 ? "" : "s"} · taxes in
                  </p>
                  {(quote.cleaning_fee || 0) > 0 && (
                    <p className="text-xs text-zinc-500">
                      Includes {cur()}
                      {inr(quote.cleaning_fee || 0)} cleaning fee
                    </p>
                  )}
                  {roomsLeft <= 2 && roomsLeft > 0 && (
                    <p className="text-xs font-medium text-rose-600">
                      Only {roomsLeft} left
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-rose-600">Sold out for these dates</p>
              )}

              {!isSite && primary && (
                <Button
                  className="w-full justify-center py-2.5 text-base"
                  disabled={!quote}
                  onClick={() => {
                    setBooking(primary.name)
                  }}
                >
                  {confirmLabel}
                </Button>
              )}

              <p className="text-center text-xs text-zinc-400">
                Check-in {p.checkin_time?.slice(0, 5)} · Check-out{" "}
                {p.checkout_time?.slice(0, 5)}
                {minNights > 1 ? ` · ${minNights} night min` : ""}
              </p>
            </div>
          </aside>
        </div>
      </div>

      {booking && (
        <Sheet
          wide
          title={done ? "Booking confirmed" : "Complete your booking"}
          description={
            done
              ? undefined
              : data.room_types.find((r) => r.name === booking)?.room_type_name
          }
          onClose={() => {
            setBooking(null)
            setDone(null)
          }}
          footer={
            done ? (
              <Button
                className="w-full justify-center py-2.5"
                onClick={() => {
                  setBooking(null)
                  setDone(null)
                }}
              >
                Done
              </Button>
            ) : (
              <Button
                className="w-full justify-center py-2.5 text-base"
                disabled={busy || !form.guest_name || !form.phone}
                onClick={submitBooking}
              >
                {busy ? "Booking…" : confirmLabel}
              </Button>
            )
          }
        >
          {done ? (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-800">
              <p className="text-lg font-semibold">{done.reservation}</p>
              <p className="mt-1 text-sm">
                Total {cur()}
                {inr(done.amount)}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  Full name
                </span>
                <input
                  className={inputCls}
                  value={form.guest_name}
                  autoFocus
                  onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  Phone
                </span>
                <input
                  className={inputCls}
                  value={form.phone}
                  placeholder="+91 …"
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  Email (optional)
                </span>
                <input
                  className={inputCls}
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </label>
              {error && (
                <p className="text-sm text-rose-600 sm:col-span-2">{error}</p>
              )}
            </div>
          )}
        </Sheet>
      )}
    </div>
  )
}
